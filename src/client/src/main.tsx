import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { startSingleSignOnListener } from "./singleSignOn";
import "./styles.css";

// Before the first render: the Neural Nexus application starts posting a
// session into this frame the moment the frame loads, and a listener registered
// from inside a component would miss those first messages.
startSingleSignOnListener();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
