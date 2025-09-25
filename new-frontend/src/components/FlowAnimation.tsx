import React, { useState, useEffect } from 'react';
import { User, Baby, FileText, Search, CheckCircle, ArrowRight } from 'lucide-react';

const FlowAnimation = () => {
  const [currentStep, setCurrentStep] = useState(0);
  const totalSteps = 3;
  
  useEffect(() => {
    const timer = setTimeout(() => {
      setCurrentStep((prevStep) => (prevStep + 1) % (totalSteps + 1));
    }, 2000);
    return () => clearTimeout(timer);
  }, [currentStep]);
  
  return (
    <div className="relative w-full h-20">
      <div className={`absolute top-0 left-0 w-full h-full flex items-center justify-center transition-opacity duration-1000 ${currentStep === 0 ? 'opacity-100' : 'opacity-0'}`}>
        <div className="flex flex-col items-center">
          <div className="flex items-center mb-3">
            <div className="bg-white rounded-full p-3 mr-4">
              <User className="h-6 w-6 text-primary" />
            </div>
            <ArrowRight className="h-6 w-6 text-white mr-4" />
            <div className="bg-white rounded-full p-3">
              <FileText className="h-6 w-6 text-primary" />
            </div>
          </div>
          <p className="text-center text-white font-medium">Description regarding text</p>
        </div>
      </div>
           
      <div className={`absolute top-0 left-0 w-full h-full flex items-center justify-center transition-opacity duration-1000 ${currentStep === 1 ? 'opacity-100' : 'opacity-0'}`}>
        <div className="flex flex-col items-center">
          <div className="flex items-center mb-3">
            <div className="bg-white rounded-full p-3 mr-4">
              <FileText className="h-6 w-6 text-primary" />
            </div>
            <ArrowRight className="h-6 w-6 text-white mr-4" />
            <div className="bg-white rounded-full p-3">
              <CheckCircle className="h-6 w-6 text-green-500" />
            </div>
          </div>
          <p className="text-center text-white font-medium">Description regarding text</p>
        </div>
      </div>
      
      <div className={`absolute top-0 left-0 w-full h-full flex items-center justify-center transition-opacity duration-1000 ${currentStep === 2 ? 'opacity-100' : 'opacity-0'}`}>
        <div className="flex flex-col items-center">
          <div className="flex flex-wrap items-center justify-center mb-3">
            <div className="bg-white rounded-full p-2 m-1">
              <Baby className="h-6 w-6 text-primary" />
            </div>
            <ArrowRight className="h-4 w-4 text-white m-1" />
            <div className="bg-white rounded-full p-2 m-1">
              <FileText className="h-6 w-6 text-primary" />
            </div>
            <ArrowRight className="h-4 w-4 text-white m-1" />
            <div className="bg-white rounded-full p-2 m-1">
              <FileText className="h-6 w-6 text-primary" />
            </div>
            <ArrowRight className="h-4 w-4 text-white m-1" />
            <div className="bg-white rounded-full p-2 m-1">
              <CheckCircle className="h-6 w-6 text-primary" />
            </div>
          </div>
          <p className="text-center text-white font-medium">Description regarding text</p>
           </div>
      </div>
      
      {/* Full complete flow */}
      <div className={`absolute top-0 left-0 w-full h-full flex items-center justify-center transition-opacity duration-1000 ${currentStep === 3 ? 'opacity-100' : 'opacity-0'}`}>
        <div className="flex flex-col items-center">
          <div className="flex flex-wrap items-center justify-center mb-6">
            <div className="bg-secondary rounded-full p-2 m-1">
              <User className="h-6 w-6 text-primary" />
            </div>
            <ArrowRight className="h-4 w-4 text-secondary m-1" />
            <div className="bg-secondary rounded-full p-2 m-1">
              <Search className="h-6 w-6 text-primary" />
            </div>
            <ArrowRight className="h-4 w-4 text-secondary m-1" />
            <div className="bg-secondary rounded-full p-2 m-1">
              <Baby className="h-6 w-6 text-primary" />
            </div>
            <ArrowRight className="h-4 w-4 text-secondary m-1" />
            <div className="bg-secondary rounded-full p-2 m-1">
              <FileText className="h-6 w-6 text-primary" />
            </div>
            <ArrowRight className="h-4 w-4 text-secondary m-1" />
            <div className="bg-secondary rounded-full p-2 m-1">
              <CheckCircle className="h-6 w-6 text-green-500" />
            </div>
          </div>
          <p className="text-center text-secondary font-medium">Description regarding text</p>
        </div>
      </div>
    </div>
  );
};

export default FlowAnimation;