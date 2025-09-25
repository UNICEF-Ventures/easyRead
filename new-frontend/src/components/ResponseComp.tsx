import { Button, Image } from "@heroui/react"
import Default from "./../assets/default.png";
import { FaArrowLeftLong } from "react-icons/fa6";
import { IoShareSocial } from "react-icons/io5";
import { BsFiletypeDocx } from "react-icons/bs";
import { FaSave } from "react-icons/fa";
import { toast } from "react-toastify";
import { clearQueryParams } from "../utils";

export default function ResponseComp({ title, results, handleExport, handleSave, handleShare, savedContentId, onBack }) {

  return (
    <div className="w-full">
      <Button startContent={<FaArrowLeftLong color="primary" />} onPress={() => {
        onBack();
        clearQueryParams();
        }} className="text-primary bg-transparent p-0 m-0">Go Back</Button>
      <h2 className="text-2xl font-semibold mb-1 text-primary uppercase">EasyRead Results</h2>
      <p className="text-sm mb-10 text-default-500">Highlighted content emphasizes importance.</p>
      <div className="flex justify-between items-center my-4">
        <h3 className="text-xl font-semibold mb-4 text-primary uppercase">Title: {title}</h3>
        <div className="flex gap-2">
          <Button className="bg-primary text-secondary m-0" startContent={<IoShareSocial color="secondary" className="text-2xl" />} onPress={()=>{
            if(!savedContentId){
              toast.error("Please save the content before sharing.");
              return
            }
            handleShare();
            }}>Share</Button>
          <Button className="bg-primary text-secondary m-0" startContent={<BsFiletypeDocx color="secondary" className="text-2xl" />} onPress={handleExport}>Export</Button>
          <Button className="bg-primary text-secondary m-0" startContent={<FaSave color="secondary" className="text-2xl"/>} onPress={handleSave}>Save</Button>
        </div>
      </div>

      {results && results.map((result, index) => (
        <div key={index} className="mb-3 border-gray-200 bg-primary/10"        
        style={{ backgroundColor: result.highlighted ? "white" : "" }} >
          <div className="grid grid-cols-12 gap-2 whitespace-pre-wrap"
                  
          >
            {result.img ? <Image
              isBlurred
              removeWrapper
              alt="Card background"
              className="object-cover col-span-2 w-full bg-secondary"
              src={Default}
              width={"100%"}
            /> : <div className="bg-primary w-full col-span-2 h-20">
            </div>}
            <p className="col-span-10 leading-relaxed align-center my-auto items-center text-justify p-2">
              {result.sentence}
            </p>
          </div>
          <div className="grid grid-cols-12 gap-2 whitespace-pre-wrap">
            <Button className="col-span-2 bg-transparent text-primary uppercase">Generate Image</Button>
          </div>
        </div>
      ))}
    </div>
  );
}