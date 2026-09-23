import { withAuth } from "next-auth/middleware";

export default withAuth({
  pages: {
    signIn: "/login",
  },
});

export const config = {
  matcher: [
    "/fleet/:path*",
    "/workspaces/:path*",
    "/ceo/:path*",
    "/settings/:path*",
  ],
};
