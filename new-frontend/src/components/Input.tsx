// MyInput.tsx
import {extendVariants, Input} from "@heroui/react";

export const UInput = extendVariants(Input, {
  variants: { // <- modify/add variants
    color: {
      stone: { // <- add a new color variant
        inputWrapper: [ // <- Input wrapper slot
          "bg-secondary",
          "focus-within:bg-secondary",
          "data-[hover=true]:bg-secondary",
          // dark theme
        //   "dark:bg-zinc-900",
        //   "dark:border-zinc-800",
        //   "dark:data-[hover=true]:bg-zinc-900",
        //   "dark:focus-within:bg-zinc-900",
        ],
        input: [  // <- Input element slot
          "text-black",
          "placeholder:text-black-600",
          // dark theme
        //   "dark:text-zinc-400",
        //   "dark:placeholder:text-zinc-600",
        ],
      },
    },
    // size: {
    //   xs: {
    //     inputWrapper: "h-6 min-h-6 px-1",
    //     input: "text-tiny",
    //   },
    //   md: {
    //     inputWrapper: "h-10 min-h-10",
    //     input: "text-small",
    //   },
    //   xl: {
    //     inputWrapper: "h-14 min-h-14",
    //     input: "text-medium",
    //   },
    // },
    radius: {
      xs: {
        inputWrapper: "rounded-lg",
      },
    },
    textSize: {
      base: {
        input: "text-base",
      },
    },
    removeLabel: {
      true: {
        label: "hidden",
      },
      false: {},
    },
  },
  defaultVariants: {
    color: "stone",
    textSize: "base",
    //removeLabel: true,
  },
});