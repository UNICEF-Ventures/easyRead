import Demo from './components/Demo';
import { useEffect, useRef, useState } from 'react';
import { AppContext } from './utils';
import "@/index.css";

import Hero from './components/Hero';
import { Card, Skeleton, useDisclosure } from '@heroui/react';
import Rules from './components/Rules';
import { ToastContainer } from "react-toastify";

function Layout() {
  const targetRef = useRef(null);
  const [showButton, setShowButton] = useState(false);
  const features = [
    {
      "title": "Async Conversion",
      "paragraph": "Upload files and let conversions run in the background. Get status updates on conversion progress."
    },
    {
      "title": "File Support",
      "paragraph": "simplify PDFs just as readily as blocks of text."
    },
    {
      "title": "LLM Simplication",
      "paragraph": "EasyRead uses state of the art LLM models to simplify text in easy-to-understand vocabulary."
    }
  ]
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          // Show button if target not visible
          setShowButton(!entry.isIntersecting);
        });
      },
      { threshold: 0.1 } // At least 10% visible
    );

    if (targetRef.current) {
      observer.observe(targetRef.current);
    }

    return () => {
      if (targetRef.current) {
        observer.unobserve(targetRef.current);
      }
    };
  }, []);

  const handleScroll = () => {
    targetRef.current?.scrollIntoView({ behavior: "smooth" });
  };


  return (<div className="min-h-screen bg-white flex flex-col">
    <Hero handleScroll={handleScroll} features={features} showButton={showButton} />
    <Demo targetRef={targetRef} />
  </div>)
}

function App({ accessToken, user, project, onVersionChange }) {
  const [items, setItems] = useState<string[]>([]);
  const { isOpen, onOpen, onOpenChange } = useDisclosure();

  useEffect(() => {
    onOpen();
  }, []);
  return (
    <AppContext.Provider value={{ items, setItems, accessToken, user, project, onVersionChange }}>
      <Layout />
      <Rules isOpen={isOpen} onOpen={onOpen} onOpenChange={onOpenChange} />
      <ToastContainer />
    </AppContext.Provider>
  );
}

export default App;