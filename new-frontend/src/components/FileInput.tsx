import { useState, useRef, DragEvent } from "react";
import { Card, Spinner } from "@heroui/react";
import { toast } from "react-toastify";

export default function FileInput({ file, setFile, loading, onFileUpload }) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    try {
      e.preventDefault();
      setIsDragging(false);
      if (e.dataTransfer.files.length > 0) {
        setFile(e.dataTransfer.files[0]);
      }
    } catch (err) {
      toast.error("An error occurred while uploading the file. Please try again.");
      return;
    }
  };

  const onChange = (e) => {
    try {
      e.preventDefault();
      setIsDragging(false);
      const filesize = ((e.target.files[0].size / 1024) / 1024).toFixed(4); // MB
      if (Number(filesize) > 20) {
        toast.error("File size exceeds 20MB limit. Please upload a smaller file.");
        return;
      }
      onFileUpload(e);
    } catch (err) {
      toast.error("An error occurred while uploading the file. Please try again.");
      return;
    }
   
  }

  return (
    <Card
      isPressable
      className={`w-full mb-3 shadow-none
        p-8  bg-[radial-gradient(circle,_#d1d5db_1px,_transparent_1px)] bg-[length:20px_20px] rounded-lg cursor-pointer
        ${isDragging ? "border-blue-500 bg-blue-50" : "bg-secondary"}
      `}
      onClick={() => fileInputRef.current?.click()} // ✅ Triggers file picker
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
    >
      <div className="text-center">
        {loading ? <Spinner label="Uploading file" classNames={{
          label: "text-primary text-sm"
        }} /> :
          file ? (
            <p className="text-primary font-medium">{file.name}</p>
          ) : (
            <>
              <p className="text-left">Drag & drop a file here</p>
              <p className="text-sm  text-left">or click to select (.pdf .md supported)</p>
            </>
          )}
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.md"
          className="hidden"
          onChange={(e) => onChange(e)}
        />
      </div>
    </Card>
  );
}
