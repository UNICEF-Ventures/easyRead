// tailwind.config.js

const { heroui } = require('@heroui/theme');

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./dist/*.html",
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    // ...
    // make sure it's pointing to the ROOT node_module
    "./node_modules/@heroui-react/theme/dist/**/*.{js,ts,jsx,tsx}",
  ],
 theme: {
    extend: {
      colors: {
        primary: "#1cabe2",
        secondary: "#fff",
        mybrand: "#ff6600",
      },
    },
  },
  darkMode: "class",
  plugins: [heroui()],
};
