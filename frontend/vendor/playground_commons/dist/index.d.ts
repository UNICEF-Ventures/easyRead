type STAGE = "prod" | "dev";
declare const getApiKey: (stage: STAGE, accessToken: string, project: string) => Promise<any>;

export { getApiKey };
