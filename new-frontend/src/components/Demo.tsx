import React, { useState } from 'react';
import { Tabs, Tab } from '@heroui/react';
import UploadForm from './UploadForm';
import ConversionHistory from './ConversionHistory';

const Demo = ({targetRef}) => {
  const [activeTab, setActiveTab] = useState<React.Key>("upload");

  return (
    <div ref={targetRef} className="mx-auto w-full pb-50 md:pb-10 bg-gray-100 h-full flex-1">
      <div className="mx-auto flex w-full flex-col items-center ">
        <Tabs id='demo' classNames={{
          tabList: "gap-0 w-full container mx-auto relative bg-secondary rounded-none p-0 px-8",
          tab: "w-fit !flex-none font-bold h-full my-0 p-0 uppercase justify-start",
          tabContent: "tracking-[1] !text-left text-gray-500 p-1 m-0 pr-18 pl-4 group-data-[selected=true]:bg-transparent group-data-[selected=true]:text-primary group-data-[selected=true]:border-b-[0.2rem] group-data-[selected=true]:border-b-primary",
          cursor: "w-0 shadow-none rounded-lg rounded-b-none group-data-[selected=true]:bg-transparent group-data-[selected=true]:text-primary ",
          panel: "container mx-auto w-full mt-2 grid grid-cols-1 md:grid-cols-3 px-8"
        }}
          className='pt-2 w-full bg-secondary'
          //@ts-ignore
          aria-label="Options" selectedKey={activeTab} onSelectionChange={setActiveTab}>
          <Tab key="upload" title="Upload" className='flex-1'>
            <UploadForm type="text" setActiveTab={setActiveTab} />
          </Tab>
          <Tab key="file-list" title="Saved Content" className='flex-1'>
            <ConversionHistory />
          </Tab>
        </Tabs>
      </div>
    </div>
  );
};

export default Demo;