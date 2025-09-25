import * as React from "react";
import { useEffect } from "react";
import DataTable from "./Table";
import { deleteSavedContent, getSavedContentByTokens, getSavedContentDetailByToken } from "../api/simplify";
import { toast } from "react-toastify";
import useEasyReadImageManager from "../hooks/useEasyReadImageManager";
import { handleExport, handleSave, handleShare } from "../utils";
import ResponseComp from "./ResponseComp";
import { Spinner } from "@heroui/react";

const LOCAL_TOKENS_KEY = 'easyread_saved_tokens';

export default function ConversionHistory() {
    const [loading, setLoading] = React.useState(true);
    const [isDeleted, setIsDeleted] = React.useState(false);

    const [savedContent, setSavedContent] = React.useState([]);
    const [markdownContent, setMarkdownContent] = React.useState('');
    const [easyReadContent, setEasyReadContent] = React.useState(null);
    const [contentTitle, setContentTitle] = React.useState('');
    const [selectedSets, setSelectedSets] = React.useState([]);
    const [preventDuplicateImages, setPreventDuplicateImages] = React.useState(true);
    const [progress, setProgress] = React.useState(false);
    const [savedContentId, setSavedContentId] = React.useState(null);
    const memoizedEasyReadContent = React.useMemo(() => easyReadContent, [easyReadContent]);
    const [loaderLabel, setLoaderLabel] = React.useState('');
    const {
        imageState,
        getCurrentImageSelections
    } = useEasyReadImageManager(memoizedEasyReadContent, null, selectedSets, preventDuplicateImages); // Pass memoized content, selected sets, and duplicate prevention setting

    const columns = [
        { name: "Preview Image", uid: "preview_image", sortable: true },
        { name: "Title", uid: "title", sortable: true },
        { name: "Sentence Count", uid: "sentence_count", sortable: true },
        { name: "Created At", uid: "created_at", sortable: true },
        { name: "ACTIONS", uid: "actions" },
    ]
    useEffect(() => {
        fetchSavedContent();
    }, [easyReadContent, savedContentId, isDeleted]);

    const readTokens = () => {
        try {
            const raw = localStorage.getItem(LOCAL_TOKENS_KEY);
            const arr = raw ? JSON.parse(raw) : [];
            return Array.isArray(arr) ? arr : [];
        } catch (e) {
            console.warn('Failed to read tokens from LocalStorage:', e);
            return [];
        }
    };

    const writeTokens = (tokens) => {
        try {
            localStorage.setItem(LOCAL_TOKENS_KEY, JSON.stringify(tokens));
        } catch (e) {
            console.warn('Failed to write tokens to LocalStorage:', e);
        }
    };

    const fetchSavedContent = async () => {
        setLoading(true);
        try {
            const tokens = readTokens();
            if (!tokens || tokens.length === 0) {
                setSavedContent([]);
            } else {
                const response = await getSavedContentByTokens(tokens);
                setSavedContent(response.data.content || []);
            }
        } catch (err) {
            console.error('Error fetching saved content:', err);
            toast.error('Failed to load saved content. Please try again later.');
        } finally {
            setLoading(false);
        }
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

    const handleDeleteContent = async (item) => {
        console.log("gggg", item);
        const id = item.id;
        const publicId = item.public_id;
        console.log("Deleting content with id:", id);

        if (!window.confirm('Are you sure you want to delete this item?')) {
            return;
        }

        try {
            await deleteSavedContent(id);
            console.log('Content deleted successfully', savedContent.filter(item => item.id !== id));
            setSavedContent(prevContent => prevContent.filter(item => item.id !== id));
            // Remove token from LocalStorage
            const tokens = readTokens();
            const updated = tokens.filter(t => t !== publicId);
            writeTokens(updated);
            toast.success('Content deleted successfully');
            setLoaderLabel("");
            setEasyReadContent(null);
            setIsDeleted(!isDeleted);
        } catch (err) {
            console.error('Error deleting content:', err);
            toast.success('Failed to delete content');
        }
    };

    const handleViewContent = async (item) => {

        try {
            const id = item.public_id;
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

    console.log("rendering conversion history", savedContent);


    return (
        <div className="col-span-1 md:col-span-2">
            {progress && <div className='w-full items-center align-center flex justify-center'><Spinner classNames={{
                label: "text-primary text-sm"
            }} label={loaderLabel} color='primary' /></div>}
            {easyReadContent && <ResponseComp onBack={() => {
                setEasyReadContent(null);
                setMarkdownContent('');
                setSavedContentId(null);
                setContentTitle('');
                setMarkdownContent('');
                setSelectedSets([]);
                setPreventDuplicateImages(true);

            }}

                results={easyReadContent} title={contentTitle} handleExport={onExport} handleSave={onSave} handleShare={() => handleShare(savedContentId)} savedContentId={savedContentId} />}

            <DataTable hide={!!easyReadContent} columns={columns} data={savedContent} loading={loading} refresh={fetchSavedContent} onDelete={handleDeleteContent} onView={handleViewContent} />

        </div>
    );
}
