import React, { useContext, useEffect, useMemo, useState } from 'react';
import { Button, Divider, Form, Spinner, Textarea } from '@heroui/react';
import FileInput from './FileInput';
import { convertFile, getDownloadUrls, getFileStatus } from '../api';
import { AppContext, handleExport, handleSave, handleShare } from '../utils';
import { generateFileNameForUser } from '../utils';
import { toast } from 'react-toastify';
import { generateEasyRead, getSavedContentDetailByToken, readMarkdownFromS3 } from '../api/simplify';
import ResponseComp from './ResponseComp';
import useEasyReadImageManager from '../hooks/useEasyReadImageManager';

interface UploadFormProps {
  setActiveTab: any;
  type: string;
}



const UploadForm: React.FC<UploadFormProps> = ({ type, setActiveTab }) => {
  const url = new URL(window.location.href);
  const id = url.searchParams.get("contentId");
  const [inputFile, setInputFile] = useState();
  const [fileLoading, setFileLoading] = useState(false);
  const [markdownContent, setMarkdownContent] = useState('');
  const [easyReadContent, setEasyReadContent] = useState(null);
  const [contentTitle, setContentTitle] = useState('');
  const [selectedSets, setSelectedSets] = useState([]);
  const [preventDuplicateImages, setPreventDuplicateImages] = useState(true);
  const [totalPages, setTotalPages] = useState(0);
  const [pagesProcessed, setPagesProcessed] = useState(0);
  const [currentProcessingStep, setCurrentProcessingStep] = useState('');
  const { accessToken, user } = useContext(AppContext);
  const [progress, setProgress] = useState(false);
  const [savedContentId, setSavedContentId] = useState(null);
  const memoizedEasyReadContent = useMemo(() => easyReadContent, [easyReadContent]);
  const [loaderLabel, setLoaderLabel] = useState('');
  const {
    imageState,
    getCurrentImageSelections
  } = useEasyReadImageManager(memoizedEasyReadContent, null, selectedSets, preventDuplicateImages); // Pass memoized content, selected sets, and duplicate prevention setting

  const handleProcessingComplete = (finalMarkdown, finalEasyRead) => {
    console.log("App: Processing complete");
    let newTitle = 'Untitled';
    let newContent = [];
    let newSelectedSets = [];
    let newPreventDuplicates = true;
    let errorMsg = "";

    // Determine final state values based on the result
    if (finalEasyRead && typeof finalEasyRead === 'object' && finalEasyRead.easy_read_sentences) {
      newTitle = finalEasyRead.title || 'Untitled';
      newContent = finalEasyRead.easy_read_sentences; // Get the final array reference
      newSelectedSets = finalEasyRead.selected_sets || [];
      newPreventDuplicates = finalEasyRead.prevent_duplicate_images ?? true;
    } else {
      newTitle = 'Processing Error';
      newContent = [];
      newSelectedSets = [];
      newPreventDuplicates = true;
      errorMsg = 'Received invalid format from easy read generation.';
      toast.error(errorMsg);
      console.error('Invalid easy read content format:', finalEasyRead);
    }

    // Update all state at once before navigating
    setMarkdownContent(finalMarkdown);
    setContentTitle(newTitle);
    setEasyReadContent(newContent);
    setSelectedSets(newSelectedSets);
    setPreventDuplicateImages(newPreventDuplicates);
    setProgress(false);
    setTotalPages(0);
    setPagesProcessed(0);
    setLoaderLabel("");

    if(errorMsg== ""){
      toast.success("Content simplified successfully.");
    }

    // Navigate after state updates
    //navigate('/results', { state: { fromProcessing: true } });
  };

  const onFileUpload = async (e: React.FormEvent) => {
    try {
      setFileLoading(true);
      //@ts-ignore
      const file = e.target.files[0];
      if (!file) {
        setFileLoading(false);
        return;
      }

      setInputFile(file);
      const fileName = generateFileNameForUser(file);
      const config = await convertFile(accessToken, "apiKey", { "email": user?.email, "fileName": fileName, "file": file });
      setLoaderLabel("Generating markdown");
      setProgress(true);
      const id = setInterval(async () => {
        const currentProgress = await getFileStatus(user, accessToken, "apiKey", config.object_key);
        if (!currentProgress || currentProgress.file_status !== "in_progress") {
          console.log("clearing interval completed", currentProgress);
          setProgress(false);
          clearInterval(id);
          getMarkdown(currentProgress);
        }
      }, 3000);

    } catch (e) {
      toast.error("Could not upload file. Try again.");
      setProgress(false);
      setLoaderLabel("");
    } finally {
      setFileLoading(false);
    }
  }

  const getMarkdown = async (config) => {
    try {
      const urls = await getDownloadUrls(config.object_key, accessToken, "apiKey");
      const text = await readMarkdownFromS3(urls.target_url);
      setMarkdownContent(text);
      toast.success("Markdown generated. You can simplify text now.");
    } catch (err) {
      console.log("err", err);
      toast.error("Could not generate markdown content. Try again.");
      setProgress(false);
      setLoaderLabel("");
    }

  }

  const handleProcessContent = async (e) => {
    e.preventDefault();
    if ((!markdownContent || markdownContent.trim() == '') && !inputFile) {
      toast.error('No content to process. Please upload a PDF or enter text.');
      return;
    }

    // Allow processing without images - in this case, no images will be retrieved/displayed
    // Make sure loading indicator from PDF extraction is off
    setFileLoading(false);

    // Use the new state for page processing
    setLoaderLabel("Processing content");
    setProgress(true); // Start page processing 
    setTotalPages(0); // Reset progress
    setPagesProcessed(0); // Reset progress

    let processingError = ""; // Track errors during page processing
    let allEasyReadSentences = [];
    let finalTitle = 'Untitled'; // Initialize title
    let firstPage = true; // Flag to capture title from the first page
    let capturedSelectedSets = Array.from(selectedSets); // Capture selected sets for image retrieval
    let capturedPreventDuplicates = preventDuplicateImages; // Capture duplicate prevention setting

    try {
      const pageBreak = "\n\n---PAGE_BREAK---\n\n";
      const markdownPages = markdownContent.split(pageBreak).filter(page => page.trim() !== ''); // Filter empty pages
      console.log(`Total pages: ${markdownPages.length}`);
      setTotalPages(markdownPages.length); // Set total pages

      for (let i = 0; i < markdownPages.length; i++) {
        const page = markdownPages[i];
        // No need to check for empty page again due to filter
        console.log(`Processing page ${i + 1} of ${markdownPages.length}`);

        // Progress callback for enhanced steps
        const onProgress = (step) => {
          console.log(`Page ${i + 1}: ${step}`);
          setCurrentProcessingStep(step);

          // Calculate sub-step progress within this page
          let stepProgress = 0;
          if (step.includes("Converting")) stepProgress = 0.25; // 25% of page
          else if (step.includes("Validating")) stepProgress = 0.50; // 50% of page  
          else if (step.includes("Revising")) stepProgress = 0.75; // 75% of page

          // Calculate total progress including sub-steps
          // For single page: i=0, so progress goes 0.25 → 0.50 → 0.75 → 1.0
          // For multi-page: distributed across all pages
          const totalProgress = i + stepProgress;
          setPagesProcessed(Math.min(totalProgress, markdownPages.length));
        };

        try {
          const response = await generateEasyRead(page, Array.from(selectedSets), onProgress);

          // Check response structure
          if (response.data && typeof response.data === 'object' && response.data.easy_read_sentences) {
            // Capture title from the first page's response
            if (firstPage && response.data.title) {
              finalTitle = response.data.title;
              firstPage = false; // Only capture title once
            }

            // Accumulate sentences only if there are any
            if (response.data.easy_read_sentences.length > 0) {
              allEasyReadSentences.push(...response.data.easy_read_sentences);
            } else {
              console.info(`Page ${i + 1} had no meaningful content to process - skipping`);
            }
          } else { // Handle page-specific error or invalid format
            console.warn("Invalid or missing easy_read_sentences for page:", response.data);
            allEasyReadSentences.push({
              sentence: `Error processing content on this page.`,
              image_retrieval: 'error'
            });
            if (!processingError) processingError = 'Some pages failed to process correctly.'; // Set a general error
          }
        } catch (pageErr) {
          console.error(`Error processing page ${i + 1}:`, pageErr);
          allEasyReadSentences.push({
            sentence: `Error processing content on this page.`,
            image_retrieval: 'error'
          });
          if (!processingError) processingError = 'Error during page processing.';
        }
        // Update progress
        setPagesProcessed(i + 1);
      }

      // If there was an error during page processing, set it now
      if (processingError) {
        console.error("Processing completed with errors:", processingError);
        toast.error(processingError);
      }

      // Prepare the final structured result for the callback
      const finalResult = {
        title: finalTitle,
        easy_read_sentences: allEasyReadSentences,
        selected_sets: capturedSelectedSets,
        prevent_duplicate_images: capturedPreventDuplicates
      };

      // Clear processing step and call completion callback
      setCurrentProcessingStep('');
      handleProcessingComplete(markdownContent, finalResult);

    } catch (err) { // Catch errors before the loop starts (e.g., splitting markdown) 
      console.error("Error during Easy Read preparation:", err);
      toast.error(err.response?.data?.error || 'Failed to start Easy Read generation.');
      // Clear state if setup fails
      setTotalPages(0);
      setPagesProcessed(0);
      setCurrentProcessingStep('');
      setProgress(false); // Explicitly turn off if setup fails
      setLoaderLabel("");
    }
    // No finally block needed here, navigation happens via callback
  };

  const onExport = async () => {
    try {
      setLoaderLabel("Exporting as .docx");
      setProgress(true);
      // Get current image selections
      const currentSelections = getCurrentImageSelections();
      await handleExport(easyReadContent, markdownContent, currentSelections, imageState, contentTitle);
    } catch (err) {
      console.error("Error exporting content:", err);
      toast.error(err.response?.data?.error || 'Failed to export content.');
    } finally {
      setLoaderLabel("");
      setProgress(false);
    }
  };

  const onSave = async () => {
    try {
      setLoaderLabel("Saving content");
      setProgress(true);
      const currentSelections = getCurrentImageSelections();
      const public_id = await handleSave(easyReadContent, markdownContent, contentTitle, currentSelections, imageState);
      setSavedContentId(public_id);
    } catch (err) {
      console.error("Error saving content:", err);
      toast.error(err.response?.data?.error || 'Failed to save content.');
    } finally {
      setLoaderLabel("");
      setProgress(false);
    }
  };

  useEffect(() => {
    const load = async () => {
      if (id && id !== '') {
        try {
          setLoaderLabel("Loading saved content");
          setProgress(true);
          const response = await getSavedContentDetailByToken(id);
          const savedValue = response?.data;
          setEasyReadContent(savedValue.easy_read_content || []);
          setContentTitle(savedValue.title || 'Untitled');
          setMarkdownContent(savedValue.markdown_content || '');
          setSavedContentId(id);
          setSelectedSets(savedValue.selected_sets || []);
          setPreventDuplicateImages(savedValue.prevent_duplicate_images ?? true);
        } catch (e) {
          console.log(e);
          toast.error("Could not load saved content. It may have been deleted.");
        } finally {
          setLoaderLabel("");
          setProgress(false);
        }
      }
    }
    load();
  }, [id]);

  return (
    <div className="col-span-1 md:col-span-2 py-3 md:py-4">
      {easyReadContent ? <ResponseComp onBack={() => {
        setEasyReadContent(null);
        setInputFile(undefined);
        setMarkdownContent('');
        setSavedContentId(null);
        setContentTitle('');
        setMarkdownContent('');
        setSelectedSets([]);
        setPreventDuplicateImages(true);

      }} results={easyReadContent} title={contentTitle} handleExport={onExport} handleSave={onSave} handleShare={() => handleShare(savedContentId)} savedContentId={savedContentId} /> : <Form onSubmit={handleProcessContent}>
        <div className="flex-1 relative w-full">
          <p className='text-sm mb-10 text-default-500'>Upload a PDF or enter markdown directly. Note all PDFs would be converted to markdown before simplifying. You can edit the generated content.</p>
          <FileInput file={inputFile} setFile={setInputFile} onFileUpload={onFileUpload} loading={fileLoading} />
          <div className='items-center max-w-full grid grid-cols-11 my-4'><Divider className='col-span-5' /> <p className='col-span-1 text-center'>OR</p> <Divider className='col-span-5' /></div>
          <Textarea isRequired={type == "text"} value={markdownContent} onChange={(e) => setMarkdownContent(e.target.value)} classNames={{
            base: "rounded-lg rounded-se-none",
            inputWrapper: "!bg-secondary data-[hover=true]:!bg-secondary group-data-[focus=true]:!bg-secondary rounded-lg hover:bg-secondary focus:bg-secondary",
          }} errorMessage={"Enter markdown content or upload a file to proceed."}
            isClearable className='hover:bg-secondary focus:bg-secondary  bg-secondary w-full mb-3' minRows={3} placeholder='Enter markdown content' label={'Markdown Content'} />
        </div>
        {progress && <div className='w-full items-center align-center flex justify-center'><Spinner classNames={{
          label: "text-primary text-sm"
        }} label={loaderLabel} color='primary' /></div>}
        <Button
          color='primary'
          type='submit'
          disabled={!markdownContent || markdownContent == '' || progress}
          className="inline-flex items-center justify-center px-10 py-3 border-transparent text-base font-medium rounded-md text-white focus:outline-none focus:ring-2 focus:ring-offset-2 shadow-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed w-full md:w-auto"
        >
          Simplify
        </Button>
      </Form>}
    </div>
  );
};

export default UploadForm;