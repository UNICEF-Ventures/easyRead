import React, { useState } from "react";
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
  Input,
  Button,
  DropdownTrigger,
  Dropdown,
  DropdownMenu,
  DropdownItem,
  Chip,
  Pagination,
  Spinner,
  useDisclosure,
  Image
} from "@heroui/react";
import axios from "axios";
import { AppContext, timeSince } from "../utils";
import { RefreshCwIcon } from "lucide-react";
import { getDownloadUrls } from "../api";
import { toast } from "react-toastify";
import { MdDelete } from "react-icons/md";
import { IoMdEye } from "react-icons/io";

export const statusOptions = [
  { name: "In Progress", uid: "In Progress" },
  { name: "Completed", uid: "completed" },
  { name: "Failed", uid: "failed" },
  { name: "Unknown", uid: "unknown" },

];

export function capitalize(s: string) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : "";
}


export const VerticalDotsIcon = ({ size = 24, width, height, ...props }) => {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      focusable="false"
      height={size || height}
      role="presentation"
      viewBox="0 0 24 24"
      width={size || width}
      {...props}
    >
      <path
        d="M12 10c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0-6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 12c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"
        fill="currentColor"
      />
    </svg>
  );
};

export const SearchIcon = (props) => {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      focusable="false"
      height="1em"
      role="presentation"
      viewBox="0 0 24 24"
      width="1em"
      {...props}
    >
      <path
        d="M11.5 21C16.7467 21 21 16.7467 21 11.5C21 6.25329 16.7467 2 11.5 2C6.25329 2 2 6.25329 2 11.5C2 16.7467 6.25329 21 11.5 21Z"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
      />
      <path
        d="M22 22L20 20"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
      />
    </svg>
  );
};

export const ChevronDownIcon = ({ strokeWidth = 1.5, ...otherProps }) => {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      focusable="false"
      height="1em"
      role="presentation"
      viewBox="0 0 24 24"
      width="1em"
      {...otherProps}
    >
      <path
        d="m19.92 8.95-6.52 6.52c-.77.77-2.03.77-2.8 0L4.08 8.95"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeMiterlimit={10}
        strokeWidth={strokeWidth}
      />
    </svg>
  );
};

const statusColorMap = {
  "In Progress": "primary",
  "Completed": "success",
};


export default function DataTable({ columns, data, loading, refresh, onView, onDelete, hide=false }) {
  const [filterValue, setFilterValue] = React.useState("");
  const [selectedKeys, setSelectedKeys] = React.useState(new Set([]));
  const [statusFilter, setStatusFilter] = React.useState("all");
  const [rowsPerPage, setRowsPerPage] = React.useState(5);

  const [sortDescriptor, setSortDescriptor] = React.useState({
    column: "created_at",
    direction: "descending",
  });
  const [page, setPage] = React.useState(1);

  const hasSearchFilter = Boolean(filterValue);
  const filteredItems = React.useMemo(() => {
    let filteredUsers = [...data];
    if (hasSearchFilter) {
      filteredUsers = filteredUsers.filter((user) =>
        user.title.toLowerCase().includes(filterValue.toLowerCase()),
      );
    }
    return filteredUsers;
  }, [data, filterValue, statusFilter]);

  const pages = Math.ceil(filteredItems.length / rowsPerPage) || 1;

  const items = React.useMemo(() => {
    const start = (page - 1) * rowsPerPage;
    const end = start + rowsPerPage;

    return filteredItems.slice(start, end);
  }, [page, filteredItems, rowsPerPage]);

  const sortedItems = React.useMemo(() => {
    const entireSortedData = [...filteredItems].sort((a, b) => {
      const first = a[sortDescriptor.column];
      const second = b[sortDescriptor.column];
      const cmp = first < second ? -1 : first > second ? 1 : 0;

      return sortDescriptor.direction === "descending" ? -cmp : cmp;
    });
    const start = (page - 1) * rowsPerPage;
    const end = start + rowsPerPage;

    return entireSortedData.slice(start, end);
  }, [sortDescriptor, items]);

  const downloadDocument = async (name, file_url, format) => {
    try {
      const response = await axios.get(`${file_url}`, {
        responseType: "blob",
      });

      const file = response.data;
      const originalFileName = name;

      //@ts-ignore
      let mimeType;
      let extensionForDownload;
      switch (format) {
        case "docx":
          mimeType =
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
          extensionForDownload = "docx";
          break;
        case "pdf":
          mimeType = "application/pdf";
          extensionForDownload = "pdf";
          break;
        case "markdown":
          mimeType = "text/markdown";
          extensionForDownload = "md";
          break;
        case "xliff":
        case "xlf":
          mimeType = "application/x-xliff+xml";
          extensionForDownload = "xliff";
          break;
        case "csv":
          mimeType = "text/csv";
          extensionForDownload = "csv";
          break;
        default:
          toast.error("Unsupported file type for download.");
          return;
      }

      //@ts-ignore
      const blob = new Blob([file], { type: mimeType });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      const originalFileNameWithoutExtension = originalFileName
        .split(".")
        .slice(0, -1)
        .join(".");

      a.download = `${originalFileNameWithoutExtension}.${extensionForDownload}`;
      a.href = url;
      a.click();
      window.URL.revokeObjectURL(url);

    } catch (e) {
      console.log(e);
      //toast.error(e.message ?? "Could not download file. Completed documents are only available for a specified amount of time after completion. File may have expired and removed. Try converting file again!")
    }
  };

  const { isOpen, onOpen, onOpenChange } = useDisclosure();


  const renderCell = React.useCallback((user, columnKey) => {
    const cellValue = user[columnKey];
    switch (columnKey) {
      case "title":
        return (<div className="capitalize">{cellValue}</div>);
      case "preview_image":
        return (
          <>{cellValue ? <Image src={cellValue} alt="Preview" className="w-20 h-auto rounded-md" /> : <div className="bg-gray-100 w-full col-span-2 h-20">
          </div>}</>
        );
      case "created_at":
        return ((new Date(cellValue)).toUTCString());
      case "model":
        return (
          <Chip className="captitalize text-primary-600" color={"primary"} size="sm" variant="flat">
            {cellValue.name}
          </Chip>
        );
      case "actions":
        return (
          <div className="relative flex justify-end items-center gap-1">
            <Button isIconOnly size="sm" variant="light" onPress={() => onView(user)}>
              <IoMdEye className="text-blue-400" size={20} />
            </Button>
            <Button isIconOnly size="sm" variant="light" onPress={() => {
              onDelete(user);
              setPage(0);
            }}>
              <MdDelete className="text-red-600" size={20} />
            </Button>

          </div>
        );
      default:
        return <div className="capitalize">{cellValue}</div>;
    }
  }, []);

  const onNextPage = React.useCallback(() => {
    if (page < pages) {
      setPage(page + 1);
    }
  }, [page, pages]);

  const onPreviousPage = React.useCallback(() => {
    if (page > 1) {
      setPage(page - 1);
    }
  }, [page]);

  const onRowsPerPageChange = React.useCallback((e) => {
    setRowsPerPage(Number(e.target.value));
    setPage(1);
  }, []);

  const onSearchChange = React.useCallback((value) => {
    if (value) {
      setFilterValue(value);
      setPage(1);
    } else {
      setFilterValue("");
    }
  }, []);

  const onClear = React.useCallback(() => {
    setFilterValue("");
    setPage(1);
  }, []);

  const topContent = React.useMemo(() => {
    return (
      <div className="flex flex-col gap-4">

        <div className="flex justify-between gap-3 items-end">
          <Input
            isClearable
            classNames={{
              label: "text-black dark:text-white",
              input: [
                "!bg-secondary",
                "hover:bg-secondary",
                "text-black dark:text-white",
                "placeholder:text-black/60 dark:placeholder:text-white/60",
              ],
              base: "flex-[0.5] rounded-lg",
              innerWrapper: "bg-secondary",
              inputWrapper: [
                "!bg-secondary",
                "hover:bg-secondary",
                "group-data-[focus=true]:bg-secondary",
                "cursor-text!",
              ],
            }}
            placeholder="Search by name"
            onClear={() => onClear()}
            onValueChange={onSearchChange}
            value={filterValue}

            startContent={
              <SearchIcon className="text-black mb-0.5 dark:text-white/90 text-black pointer-events-none shrink-0" />
            }
          />
          <div className="flex gap-3">
            <Button color="primary" className="text-secondary" onPress={refresh} endContent={<RefreshCwIcon style={{ width: "1rem" }} />}>
              Refresh
            </Button>
          </div>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-black text-small">Total {data.length} items</span>
          <label className="flex items-center text-black text-small">
            Rows per page:
            <select
              className="bg-transparent outline-hidden text-black text-small"
              onChange={onRowsPerPageChange}
            >
              <option value="5">5</option>
              <option value="10">10</option>
              <option value="15">15</option>
            </select>
          </label>
        </div>
      </div>
    );
  }, [
    filterValue,
    statusFilter,
    onRowsPerPageChange,
    data.length,
    onSearchChange,
    hasSearchFilter,
  ]);

  const bottomContent = React.useMemo(() => {
    return (
      <div className="py-2 px-2 flex justify-center items-center">
        <Pagination
          isCompact
          showControls
          showShadow
          color="primary"
          page={page}
          total={pages}
          onChange={setPage}
          classNames={{
            wrapper: "bg-secondary shadow-none ",
            item: "bg-secondary text-black shadow-none",
            prev: "bg-secondary text-black shadow-none",
            next: "bg-secondary text-black shadow-none"
          }}
        />
        {/* <div className="hidden sm:flex w-[30%] justify-end gap-2">
          <Button isDisabled={pages === 1} size="sm" variant="bordered" color="primary" onPress={onPreviousPage}>
            Previous
          </Button>
          <Button isDisabled={pages === 1} size="sm" variant="bordered" color="primary" onPress={onNextPage}>
            Next
          </Button>
        </div> */}
      </div>
    );
  }, [selectedKeys, items.length, page, pages, hasSearchFilter]);


  return (
    <Table
      isHeaderSticky
      aria-label="Example table with custom cells, pagination and sorting"
      bottomContent={bottomContent}
      bottomContentPlacement="outside"
      classNames={{
        wrapper: "shadow-none rounded-lg",
      }}
      style={{
        display: hide ? "none": "block",
      }}
      // selectedKeys={selectedKeys}
      // selectionMode="multiple"
      sortDescriptor={sortDescriptor}
      topContent={topContent}
      topContentPlacement="outside"
      onSelectionChange={setSelectedKeys}
      onSortChange={setSortDescriptor}

    >
      <TableHeader columns={columns}>
        {(column) => (
          <TableColumn
            className="text-[0.8rem] bg-primary text-secondary"
            key={column.uid}
            align={column.uid === "actions" ? "center" : "start"}
            allowsSorting={column.sortable}
          >
            {column.name}
          </TableColumn>
        )}
      </TableHeader>
      <TableBody emptyContent={"No saved content"} items={sortedItems} loadingContent={<Spinner color="primary" />} isLoading={loading}>
        {(item) => (
          <TableRow key={item.object_key} >
            {(columnKey) => <TableCell className="text-black">{renderCell(item, columnKey)}</TableCell>}
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}