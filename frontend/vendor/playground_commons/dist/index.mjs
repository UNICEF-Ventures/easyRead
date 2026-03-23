// src/index.ts
import axios from "axios";
var getApiKey = async (stage, accessToken, project) => {
  try {
    const { data } = await axios.post(
      `https://xgfsn44497.execute-api.eu-north-1.amazonaws.com/${stage}/playground-create-api-key`,
      {
        project
      },
      {
        headers: {
          Accept: "*/*",
          "Content-Type": "application/json",
          "Authorization": `Bearer ${accessToken}`
        }
      }
    );
    return data["api_key"];
  } catch (error) {
    console.error("Error", error);
    throw error;
  }
};
export {
  getApiKey
};
//# sourceMappingURL=index.mjs.map