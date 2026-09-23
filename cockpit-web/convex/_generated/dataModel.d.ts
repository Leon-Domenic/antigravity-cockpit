import type {
  DataModelFromSchemaDefinition,
  GenericDataModel,
} from "convex/server";
import type schema from "../schema";

export type DataModel = DataModelFromSchemaDefinition<typeof schema>;
export type Doc<TableName extends string> = any;
export type Id<TableName extends string> = string & { __tableName?: TableName };
