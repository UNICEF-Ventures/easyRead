import FlowAnimation from './FlowAnimation';
import { Accordion, AccordionItem, Link, Select, SelectItem } from '@heroui/react';
import { useContext, useEffect, useRef, useState } from 'react';
import { AppContext } from '../utils';
import { IoIosArrowForward } from "react-icons/io";

const Hero = ({ handleScroll, showButton, features }) => {
  const { project, onVersionChange } = useContext(AppContext);
  const currentPath = window.location.pathname;

  return (
    <section className="py-4 mt-4 md:mt-8">
      <div className="container mx-auto px-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-1 md:gap-20">
          <div className="w-full mb-10 md:mb-0 col-span-2">
            <div className='w-full flex items-center gap-[0.4rem]'>
              <h1 className="text-3xl lg:text-3xl font-bold leading-tight text-black capitalize">
                {project.name}
              </h1>
              {project.versions && project.versions.length > 0 && <Select
                classNames={{
                  "base": "w-fit rounded-2xl text-black !bg-gray-100",
                  "trigger": "justify-start items-center min-w-0 w-fit px-[0.34rem] py-1 h-fit min-h-0 !bg-gray-100 ",
                  "mainWrapper": "w-fit rounded-2xl !bg-gray-100 ",
                  "innerWrapper": "p-0 m-0 min-w-0 w-fit !bg-gray-100 ",
                  "value": "w-fit p-0 pr-6 !text-black",
                  "listbox": "!bg-gray-100",
                  "popoverContent": "p-0 !bg-gray-100  !text-black",

                }}
                className="text-xs/5 font-bold"
                defaultSelectedKeys={project.versions.filter((version) => currentPath == project.link + version.path).map(version => version.name) ?? [project.versions[0].name]}
                onSelectionChange={(keys) => {
                  const selectedKey = keys.values().next().value;
                  const selectedVersionLink = project.versions.filter(version => version.name == selectedKey)[0].path;
                  onVersionChange(project.link + selectedVersionLink);
                }}
              >
                {project.versions.map((version) => (
                  <SelectItem className='px-2 py-0 w-fit text-xs data-[hover=true]:bg-transparent data-[hover=true]:text-black data-[selectable=true]:focus:bg-transparent data-[selectable=true]:focus:text-black' key={version.name}>{version.name}</SelectItem>
                ))}
              </Select>}
            </div>


            <p className="text-lg mb-0 text-black ">
              {project.description}
            </p>
            <div className="flex flex-col sm:flex-row gap-4">
              {showButton && <Link
                //href="#demo"
                onPress={handleScroll}
                className="inline-flex sm:bg-red-400 items-center justify-center px-4 py-2 border border-primary bg-primary  font-medium rounded-md text-secondary hover:bg-white/10"
              >
                Jump to Demo
              </Link>}
            </div>
          </div>
          {/* <div className="w-full ">
            <div className="bg-primary rounded-lg p-8">
              <FlowAnimation />
            </div>
          </div> */}
        </div>
        <Accordion variant="light" className='p-0 !w-fit'>
          <AccordionItem key="1" aria-label="Accordion 1" indicator={<IoIosArrowForward/>} classNames={{
            trigger:"gap-0 p-0 w-fit py-2",
            indicator:"text-primary text-md display-none p-0",
            title: "text-base font-medium w-fit  py-0 text-primary"
          }} title={"Learn More"}>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-1 md:gap-20 mt-1">
              {features.map((feature => (<div className="py-4 bg-secondary">
                <div className='flex items-center gap-4'>
                  <h3 className="text font-bold mb-1 capitalize ">{feature.title}</h3>
                </div>
                <p className="text-sm text-black text-justify">
                  {feature.paragraph}
                </p>
              </div>)))}
            </div>
          </AccordionItem>

        </Accordion>

      </div>

    </section>
  );
};

export default Hero;