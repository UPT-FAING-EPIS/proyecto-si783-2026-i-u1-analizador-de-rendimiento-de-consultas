import { ConnectionPayload } from "./apiClient";

export interface QueryAnalyzerProfile {
  name: string;
  connection: ConnectionPayload;
}

export type ProfilesConfig = Record<string, ConnectionPayload>;

export const SUPPORTED_ENGINES = [
  "postgresql",
  "mysql",
  "sqlite",
  "mongodb",
  "redis",
  "cockroachdb",
  "yugabytedb",
  "neo4j",
  "influxdb",
  "elasticsearch",
  "mssql"
] as const;

export function profilesFromConfig(profiles: ProfilesConfig | undefined): QueryAnalyzerProfile[] {
  return Object.entries(profiles ?? {})
    .filter(([name]) => name.trim().length > 0)
    .map(([name, connection]) => ({ name, connection }))
    .sort((left, right) => left.name.localeCompare(right.name));
}

export function upsertProfile(
  profiles: ProfilesConfig | undefined,
  profile: QueryAnalyzerProfile
): ProfilesConfig {
  return {
    ...(profiles ?? {}),
    [profile.name]: profile.connection
  };
}

export function defaultPortForEngine(engine: string): number | undefined {
  const ports: Record<string, number> = {
    postgresql: 5432,
    mysql: 3306,
    mongodb: 27017,
    redis: 6379,
    neo4j: 7687,
    elasticsearch: 9200,
    mssql: 1433
  };

  return ports[engine];
}

export function buildProfileDescription(profile: QueryAnalyzerProfile): string {
  const { engine, host, port, database } = profile.connection;
  const endpoint = host ? `${host}${port ? `:${port}` : ""}` : "";
  return [engine, endpoint, database].filter(Boolean).join(" - ");
}
