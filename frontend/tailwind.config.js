/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        agent: {
          planner: "#3b82f6",
          executor: "#8b5cf6",
          validator: "#10b981",
          retriever: "#f59e0b"
        }
      }
    },
  },
  plugins: [],
}
