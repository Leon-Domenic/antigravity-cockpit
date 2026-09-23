import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import GithubProvider from "next-auth/providers/github";
import bcrypt from "bcryptjs";
import { convexHttp } from "./convex";
import { api } from "../convex/_generated/api";

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: "Local Credentials",
      credentials: {
        email: { label: "Email", type: "email", placeholder: "admin@webigo.ai" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          throw new Error("Email and password are required");
        }

        const email = credentials.email.toLowerCase().trim();
        const password = credentials.password;

        // Try fetching user from local Convex DB
        let user: any = null;
        try {
          user = await convexHttp.query(api.users.getUserByEmail, { email });
        } catch (err) {
          console.warn("[NextAuth] Convex query error, checking fallback/seeding:", err);
        }

        // If no user exists yet and credentials match default admin, auto-seed admin
        if (!user && email === "admin@webigo.ai" && password === "antigravity") {
          const hash = await bcrypt.hash("antigravity", 10);
          try {
            const seededId = await convexHttp.mutation(api.users.seedDefaultAdmin, {
              email: "admin@webigo.ai",
              name: "Cockpit Administrator",
              passwordHash: hash,
            });
            return {
              id: seededId || "admin-root",
              name: "Cockpit Administrator",
              email: "admin@webigo.ai",
              role: "admin",
            };
          } catch (e) {
            // Return ephemeral session if Convex DB connection is starting up
            return {
              id: "admin-root",
              name: "Cockpit Administrator",
              email: "admin@webigo.ai",
              role: "admin",
            };
          }
        }

        if (!user) {
          throw new Error("Invalid email or password");
        }

        // Verify password hash
        const isValid = await bcrypt.compare(password, user.passwordHash);
        if (!isValid) {
          throw new Error("Invalid email or password");
        }

        return {
          id: user._id,
          name: user.name,
          email: user.email,
          role: user.role || "developer",
          image: user.image,
        };
      },
    }),

    ...(process.env.GITHUB_ID && process.env.GITHUB_SECRET
      ? [
          GithubProvider({
            clientId: process.env.GITHUB_ID,
            clientSecret: process.env.GITHUB_SECRET,
            authorization: {
              params: {
                scope: "read:user user:email repo",
              },
            },
          }),
        ]
      : []),
  ],

  pages: {
    signIn: "/login",
    error: "/login",
  },

  session: {
    strategy: "jwt",
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },

  callbacks: {
    async signIn({ user, account, profile }) {
      if (account?.provider === "github" && account.access_token) {
        // Automatically persist GitHub OAuth token into Convex gitConfigs
        // so agents and cockpit can clone private repositories immediately
        try {
          await convexHttp.mutation(api.git.saveGitConfig, {
            provider: "github",
            token: account.access_token,
            username: (profile as any)?.login || user.name || "github-user",
            email: user.email || "",
          });
        } catch (err) {
          console.error("[NextAuth] Failed to sync GitHub access token to Convex:", err);
        }
      }
      return true;
    },

    async jwt({ token, user }) {
      if (user) {
        token.id = user.id;
        token.role = (user as any).role || "admin";
      }
      return token;
    },

    async session({ session, token }) {
      if (session.user) {
        (session.user as any).id = token.id;
        (session.user as any).role = token.role || "admin";
      }
      return session;
    },
  },

  secret: process.env.NEXTAUTH_SECRET || "webigo-workspaces-secret-local-proxmox-key-2026",
};
