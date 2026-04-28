import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TransactionProvider } from "ethereum-identity-kit";
import "ethereum-identity-kit/css";
import { WagmiProvider } from "wagmi";

import App from "./App";
import "./styles.css";
import { wagmiConfig } from "./wagmi";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <WagmiProvider config={wagmiConfig}>
        <TransactionProvider>
          <App />
        </TransactionProvider>
      </WagmiProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
