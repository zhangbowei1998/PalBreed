import React from "react";
import ReactDOM from "react-dom/client";
import { XProvider } from "@ant-design/x";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <XProvider theme={{ token: { colorPrimary: "#111111" } }}>
      <App />
    </XProvider>
  </React.StrictMode>,
);
