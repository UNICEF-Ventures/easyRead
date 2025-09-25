import axios from "axios";
import { toast } from "react-toastify";

const BASE_URL = import.meta.env.VITE_API_URL;

export const getPreSignedUrl = async (action, fileName, token, apiKey) => {
  try {
    const response = await axios.post(`${BASE_URL}?action=get-presigned-url`, {
      name: fileName,
      client_action: action,
    }, {
      headers: {
        "x-api-key": apiKey,
        "Authorization": `Bearer ${token}`
      }
    });
    const url = response.data;
    return url;
  } catch (e) {
    console.log(e);
    if (axios.isAxiosError(e)) {
      if (e.response && e.response.status === 429) {
        console.error('❌ Rate limit hit (429):', e.response.data);
        throw Error('Too many requests. Please try again later.');
      }
    }
    throw Error("Could not download file. Completed documents are only available for a specified amount of time after completion. File may have expired and removed. Try converting file again!");
  }
};

export const getDownloadUrls = async (fileName, token, apiKey) => {
  try {
    const response = await axios.post(`${BASE_URL}?action=get-download-urls`, {
      object_key: fileName,
    }, {
      headers: {
        "x-api-key": apiKey,
        "Authorization": `Bearer ${token}`
      }
    });
    const url = response.data;
    return url;
  } catch (e) {
    console.log(e);
    if (axios.isAxiosError(e)) {
      if (e.response && e.response.status === 429) {
        console.error('❌ Rate limit hit (429):', e.response.data);
        throw Error('Too many requests. Please try again later.');
      }
    }
    throw Error("Could not download file. Completed documents are only available for a specified amount of time after completion. File may have expired and removed. Try converting file again!");
  }
};

export const queue_file = async (token, apiKey, fileName, email) => {
  try {
    const getUrlValue = (await getPreSignedUrl("get_object", fileName, token, apiKey)) ?? null;
    const putUrlValue = (await getPreSignedUrl("put_object", fileName, token, apiKey)) ?? null;

    if (!getUrlValue || !putUrlValue) {
      toast.error(
        "Could not process file. Refresh and try again!"
      );
      return;
    }

    const body = {
      username: email,
      object_key: fileName,
      source_format: "pdf",
      target_format: "markdown",
      source_url: getUrlValue,
    }
   
    const res = await axios.post(`${BASE_URL}?action=upload-config`, body, {
      headers: {
        "x-api-key": apiKey,
        "Authorization": `Bearer ${token}`
      }
    });
    if (res.status == 200) {
      return {"putUrlValue": putUrlValue, "data": res.data};
    } else {
      throw new DOMException("Something went wrong! Could not upload file. Try again");
    }
  } catch (e) {
    console.log(e);
    throw e;
  }
};

export const convertFile = async (token, apiKey, body) => {
  try {

    const fileName = body.fileName;
    const email = body.email;
    const uploadedFile = body.file;

    const res = await queue_file(token, apiKey, fileName, email);
    const putUrl = res?.putUrlValue ?? null;
    const config = res?.data ?? null;

    if (!putUrl) {
     throw new Error(
        "Could not upload file for conversion. Refresh and try again!"
      );
    }

    await axios.put(putUrl, uploadedFile, {
      headers: {
        'Content-Type': uploadedFile.type,
      }
    });
    return config;
  } catch (e) {
    console.log(e);
    if (axios.isAxiosError(e)) {
      if (e.response && e.response.status === 429) {
        console.error('❌ Rate limit hit (429):', e.response.data);
        throw new Error('Too many requests. Please try again later.');
      }
    }
    throw new Error("Something went wrong converting file. Try again!");
  }
};

export const getFiles = async (user, token, apiKey) => {
  try {
    const res = await axios.post(`${BASE_URL}?action=get-user-files`, {
      username: user.email
    }, {
      headers: {
        "x-api-key": apiKey,
        "Authorization": `Bearer ${token}`
      }
    });
    let files = res.data;
    files = files.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    return files;
  } catch (e) {
    console.log(e);
    if (axios.isAxiosError(e)) {
      if (e.response && e.response.status === 429) {
        console.error('❌ Rate limit hit (429):', e.response.data);
        throw Error('Too many requests. Please try again later.');
      }
    }
    throw e;
  }
};

export const getFileStatus = async (user, token, apiKey, fileName) => {
  try {
    const res = await axios.post(`${BASE_URL}?action=load-config`, {
      username: user.email,
      object_key: fileName
    }, {
      headers: {
        "x-api-key": apiKey,
        "Authorization": `Bearer ${token}`
      }
    });
    let files = res.data;
    console.log("file status", files);
    return files;
  } catch (e) {
    console.log(e);
    if (axios.isAxiosError(e)) {
      if (e.response && e.response.status === 429) {
        console.error('❌ Rate limit hit (429):', e.response.data);
        throw Error('Too many requests. Please try again later.');
      }
    }
    throw e;
  }
};