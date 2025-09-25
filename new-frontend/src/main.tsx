import React, { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import { HeroUIProvider } from "@heroui/react";

const accessToken = import.meta.env.VITE_ACCESS_TOKEN;

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <HeroUIProvider>
      <App project={{
        key: "sample",
        name: "EasyRead",
        path: "sample",
        description: "Easy Read is a way of writing that makes information easier to understand for people who may find standard text difficult. It uses short sentences, simple words, and supportive images to explain ideas step by step. The focus is on clarity and inclusion, so that everyone can access and engage with important information.",
        color: "#75649b",
        link: "/sample",
        state: "sample",
        technologies: ["X", "Y"],
        enabled: true,
        category: "other",
      }} onVersionChange={() => { }} 
      accessToken={accessToken} user={{email: "playground@unicef.org"}}/>
    </HeroUIProvider>
  </StrictMode>
);
