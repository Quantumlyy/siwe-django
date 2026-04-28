import { createAppKit } from "@reown/appkit/react";
import { WagmiAdapter } from "@reown/appkit-adapter-wagmi";
import {
  defineChain,
  mainnet as appKitMainnet,
  sepolia as appKitSepolia,
  type AppKitNetwork,
} from "@reown/appkit/networks";
import { createConfig, http } from "wagmi";
import { hardhat, mainnet, sepolia } from "wagmi/chains";
import { injected } from "wagmi/connectors";

export const reownProjectId = import.meta.env.VITE_REOWN_PROJECT_ID || "";
export const hasReownProjectId = Boolean(reownProjectId);

const appOrigin =
  typeof window === "undefined" ? "http://localhost:5173" : window.location.origin;

const appKitHardhat = defineChain({
  id: 31337,
  caipNetworkId: "eip155:31337",
  chainNamespace: "eip155",
  name: "Hardhat",
  nativeCurrency: {
    decimals: 18,
    name: "Ether",
    symbol: "ETH",
  },
  rpcUrls: {
    default: { http: ["http://127.0.0.1:8545"] },
  },
});

const appKitNetworks = [
  appKitMainnet,
  appKitSepolia,
  appKitHardhat,
] as [AppKitNetwork, ...AppKitNetwork[]];

const metadata = {
  name: "siwe-django showcase",
  description: "Django session authentication with Sign-In with Ethereum.",
  url: appOrigin,
  icons: [],
};

const fallbackConfig = createConfig({
  chains: [mainnet, sepolia, hardhat],
  connectors: [injected()],
  transports: {
    [mainnet.id]: http(),
    [sepolia.id]: http(),
    [hardhat.id]: http("http://127.0.0.1:8545"),
  },
});

const appKitAdapter = hasReownProjectId
  ? new WagmiAdapter({
      networks: appKitNetworks,
      projectId: reownProjectId,
    })
  : null;

if (appKitAdapter) {
  createAppKit({
    adapters: [appKitAdapter],
    networks: appKitNetworks,
    projectId: reownProjectId,
    metadata,
    features: {
      analytics: false,
    },
  });
}

export const wagmiConfig = appKitAdapter?.wagmiConfig ?? fallbackConfig;
