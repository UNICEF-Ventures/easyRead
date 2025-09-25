import { createContext } from "react";
import { toast } from "react-toastify";
import { exportCurrentContentDocx, saveContent } from "./api/simplify";

export type AppContextType = {
  items: string[];
  setItems: React.Dispatch<React.SetStateAction<string[]>>;
  project: any;
  onVersionChange: any;
  accessToken: string;
  user: any;
};

export const AppContext = createContext<AppContextType>({ items: [], setItems: () => { }, accessToken: "", user: {}, project: {}, onVersionChange: () => { } });


function randomString(length) {
  let result = '';
  const characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  const charactersLength = characters.length;
  let counter = 0;
  while (counter < length) {
    result += characters.charAt(Math.floor(Math.random() * charactersLength));
    counter += 1;
  }
  return result;
}

export function generateFileNameForUser(file: File) {
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hour = String(date.getHours()).padStart(2, '0');
  const min = String(date.getMinutes()).padStart(2, '0');
  const sec = String(date.getSeconds()).padStart(2, '0');

  const randomPrefix = randomString(6);
  const name = file.name.replace(/ /g, '+');
  const formattedDate = `${day}${month}${year}_${hour}${min}${sec}`;
  return `${randomPrefix}-${formattedDate}-${name}`;
}

export function timeSince(date: string) {
  const utcDate = new Date(date + "Z") // Adding "Z" ensures it's treated as UTC
  const current_date_utc = utcDate.getTime()
  const seconds = Math.floor((Date.now() - current_date_utc) / 1000)
  let interval = seconds / 31536000
  if (isNaN(interval)) {
    return "---"
  }
  if (interval > 1) {
    return Math.floor(interval) + " year" + (interval < 2 ? "" : "s ago")
  }
  interval = seconds / 2592000
  if (interval > 1) {
    return Math.floor(interval) + " month" + (interval < 2 ? "" : "s ago")
  }
  interval = seconds / 86400
  if (interval > 1) {
    return Math.floor(interval) + " day" + (interval < 2 ? "" : "s ago")
  }
  interval = seconds / 3600
  if (interval > 1) {
    return Math.floor(interval) + " hour" + (interval < 2 ? "" : "s ago")
  }
  interval = seconds / 60
  if (interval > 1) {
    return Math.floor(interval) + " minute" + (interval < 2 ? "" : "s ago")
  }
  return Math.floor(seconds) + " second" + (seconds < 2 ? "" : "s ago")
}

export const handleShare = async (savedContentId) => {
  try {
    const url = new URL(window.location.href);
    const baseUrl = url.origin + url.pathname;
    const currentUrl = baseUrl + `?contentId=${savedContentId}`;
    await navigator.clipboard.writeText(currentUrl);
    toast.success("URL copied to clipboard!");
  } catch (err) {
    console.error('Failed to copy URL to clipboard:', err);
    // Fallback for browsers that don't support clipboard API
    try {
      const textArea = document.createElement('textarea');
      textArea.value = window.location.href;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      toast.success("URL copied to clipboard!");
    } catch (fallbackErr) {
      console.error('Fallback copy also failed:', fallbackErr);
      toast.error("Failed to copy URL.");
    }
  }
};



export const handleSave = async (easyReadContent, markdownContent, contentTitle, currentSelections, imageState) => {
  if (!markdownContent || easyReadContent.length === 0) {
    toast.error("Content missing, cannot save.");
    return;
  }
  // Construct the JSON to save, including the selected image path from the current selections
  const dataToSave = easyReadContent.map((item, index) => {
    const finalSelectedPath = currentSelections[index] || imageState[index]?.selectedPath || null;

    return {
      ...item,
      selected_image_path: finalSelectedPath,
      alternative_images: imageState[index]?.images?.map(img => img.url) || []
    };
  });

  try {
    const response = await saveContent(contentTitle, markdownContent, dataToSave);
    console.log('Save response:', response.data);
    // Store token in LocalStorage
    const token = response.data?.public_id;
    if (token) {
      try {
        const key = 'easyread_saved_tokens';
        const raw = localStorage.getItem(key);
        const arr = raw ? JSON.parse(raw) : [];
        if (!arr.includes(token)) {
          arr.push(token);
          localStorage.setItem(key, JSON.stringify(arr));
        }
      } catch (e) {
        console.warn('Failed to persist token to LocalStorage:', e);
      }
    }
    toast.success("Content saved successfully!");
    return response.data?.public_id || null;
    // Redirect to the saved content page after successful save
  } catch (err) {
    console.error("Error saving content:", err);
    toast.error(err.response?.data?.error || 'Failed to save content.');
  }
};


export const handleExport = async (easyReadContent, markdownContent, currentSelections, imageState, contentTitle) => {
  if (!markdownContent || easyReadContent.length === 0) {
    toast.error("Content missing, cannot export.");
    return;
  }

  try {
    // Prepare content with selected images
    const contentToExport = easyReadContent.map((item, index) => {
      const finalSelectedPath = currentSelections[index] || imageState[index]?.selectedPath || null;
      return {
        ...item,
        selected_image_path: finalSelectedPath
      };
    });

    const response = await exportCurrentContentDocx(contentTitle, contentToExport, markdownContent);

    // Create download link
    const blob = new Blob([response.data], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;

    // Generate filename
    const safeTitle = (contentTitle || 'easyread_document').replace(/[^a-zA-Z0-9\-_]/g, '_').toLowerCase();
    link.download = `${safeTitle}.docx`;

    document.body.appendChild(link);
    link.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(link);

  } catch (err) {
    console.error("Error exporting content:", err);
    toast.error(err.response?.data?.error || 'Failed to export content.');
  }
};


export const clearQueryParams = () => {
  const url = new URL(window.location.href);
  url.search = '';
  window.history.replaceState({}, document.title, url.toString());
}