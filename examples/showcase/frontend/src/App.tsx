import { FormEvent, useMemo, useState } from "react";
import { AppKitButton, AppKitNetworkButton } from "@reown/appkit/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ProfileCard, useSiwe } from "ethereum-identity-kit";
import {
  AlertCircle,
  BadgeCheck,
  Copy,
  ExternalLink,
  Link as LinkIcon,
  LogOut,
  RefreshCw,
  Search,
  ShieldCheck,
  Unlink,
  UserRound,
  Wallet,
} from "lucide-react";
import { useAccount, useChainId, useConnect, useDisconnect } from "wagmi";

import {
  fetchPublicProfile,
  fetchSession,
  getLastNonceMetadata,
  getNonce,
  linkSignature,
  logout,
  SessionResponse,
  unlinkWallet,
  verifySignature,
  WalletIdentity,
} from "./api";
import { hasReownProjectId } from "./wagmi";

function shortAddress(address?: string) {
  if (!address) return "Not connected";
  return `${address.slice(0, 6)}...${address.slice(-4)}`;
}

function formatDate(value: string | null) {
  if (!value) return "Never";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function copyText(value: string) {
  void navigator.clipboard?.writeText(value);
}

function WalletAvatar({ wallet }: { wallet: WalletIdentity | null }) {
  if (wallet?.avatar) {
    return <img className="avatar" src={wallet.avatar} alt="" />;
  }
  return (
    <div className="avatar avatarFallback" aria-hidden="true">
      <Wallet size={28} />
    </div>
  );
}

function StatusPill({
  active,
  children,
}: {
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <span className={active ? "pill pillActive" : "pill"}>
      {active ? <BadgeCheck size={14} /> : <AlertCircle size={14} />}
      {children}
    </span>
  );
}

function WalletRow({
  wallet,
  canUnlink,
  onUnlink,
  isPending,
}: {
  wallet: WalletIdentity;
  canUnlink: boolean;
  onUnlink: () => void;
  isPending: boolean;
}) {
  return (
    <div className="walletRow">
      <div className="walletMain">
        <WalletAvatar wallet={wallet} />
        <div>
          <div className="rowTitle">{wallet.displayName}</div>
          <div className="muted mono">{wallet.caip10}</div>
        </div>
      </div>
      <div className="walletActions">
        <StatusPill active={wallet.isPrimary}>
          {wallet.isPrimary ? "Primary" : "Linked"}
        </StatusPill>
        <button
          className="iconButton"
          type="button"
          title="Copy address"
          onClick={() => copyText(wallet.address)}
        >
          <Copy size={16} />
        </button>
        {canUnlink ? (
          <button
            className="iconButton danger"
            type="button"
            title="Unlink wallet"
            disabled={isPending}
            onClick={onUnlink}
          >
            <Unlink size={16} />
          </button>
        ) : null}
      </div>
    </div>
  );
}

function GateList({ session }: { session: SessionResponse }) {
  return (
    <div className="gateGrid">
      {session.gates.map((gate) => (
        <div className="gateItem" key={gate.name}>
          <div>
            <div className="rowTitle">{gate.label}</div>
            <div className="muted">{gate.description || gate.group}</div>
          </div>
          <StatusPill active={gate.active}>
            {gate.active ? "Granted" : "Closed"}
          </StatusPill>
        </div>
      ))}
      {session.gates.length === 0 ? (
        <div className="empty">No token gates configured.</div>
      ) : null}
    </div>
  );
}

export default function App() {
  const queryClient = useQueryClient();
  const account = useAccount();
  const chainId = useChainId();
  const { connect, connectors, isPending: isConnecting } = useConnect();
  const { disconnect } = useDisconnect();
  const [siweError, setSiweError] = useState("");
  const [profileQuery, setProfileQuery] = useState("vitalik.eth");

  const sessionQuery = useQuery({
    queryKey: ["showcase-session"],
    queryFn: fetchSession,
  });

  const refreshSession = () =>
    queryClient.invalidateQueries({ queryKey: ["showcase-session"] });

  const signIn = useSiwe({
    getNonce,
    verifySignature: async (message, _nonce, signature) => {
      await verifySignature(message, signature);
    },
    message: "Sign in to the siwe-django showcase.",
    expirationTime: 300000,
    onSignInSuccess: () => {
      setSiweError("");
      refreshSession();
    },
    onSignInError: (error) => setSiweError(error.message),
  });

  const linkWallet = useSiwe({
    getNonce,
    verifySignature: async (message, _nonce, signature) => {
      await linkSignature(message, signature);
    },
    message: "Sign in to the siwe-django showcase.",
    expirationTime: 300000,
    onSignInSuccess: () => {
      setSiweError("");
      refreshSession();
    },
    onSignInError: (error) => setSiweError(error.message),
  });

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: () => refreshSession(),
  });

  const unlinkMutation = useMutation({
    mutationFn: unlinkWallet,
    onSuccess: () => refreshSession(),
  });

  const publicProfile = useMutation({
    mutationFn: fetchPublicProfile,
  });

  const session = sessionQuery.data;
  const primaryWallet = session?.wallet ?? null;
  const nonceMetadata = getLastNonceMetadata();
  const addressOrName = primaryWallet?.ethereumIdentityKit.addressOrName;

  const connectedLabel = useMemo(() => {
    if (!account.address) return "No wallet connected";
    return `${shortAddress(account.address)} on chain ${chainId}`;
  }, [account.address, chainId]);

  function submitProfileSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (profileQuery.trim()) {
      publicProfile.mutate(profileQuery.trim());
    }
  }

  return (
    <main className="appShell">
      <section className="topBar" aria-label="SIWE dashboard header">
        <div>
          <div className="eyebrow">siwe-django showcase</div>
          <h1>Wallet session dashboard</h1>
        </div>
        <div className="toolbar">
          <button
            className="iconButton"
            type="button"
            title="Refresh session"
            onClick={refreshSession}
          >
            <RefreshCw size={18} />
          </button>
          {session?.authenticated ? (
            <button
              className="commandButton secondary"
              type="button"
              disabled={logoutMutation.isPending}
              onClick={() => logoutMutation.mutate()}
            >
              <LogOut size={16} />
              Logout
            </button>
          ) : null}
        </div>
      </section>

      <section className="dashboardGrid">
        <div className="panel identityPanel">
          <div className="panelHeader">
            <div>
              <h2>Session</h2>
              <p>{connectedLabel}</p>
            </div>
            <StatusPill active={Boolean(session?.authenticated)}>
              {session?.authenticated ? "Signed in" : "Signed out"}
            </StatusPill>
          </div>

          <div className="identityHero">
            <WalletAvatar wallet={primaryWallet} />
            <div>
              <div className="displayName">
                {primaryWallet?.displayName || "Connect and sign a SIWE message"}
              </div>
              <div className="muted mono">
                {primaryWallet?.caip10 || account.address || "No wallet address"}
              </div>
            </div>
          </div>

          <div className="statsGrid">
            <div>
              <span>Followers</span>
              <strong>{primaryWallet?.profile.followersCount ?? 0}</strong>
            </div>
            <div>
              <span>Following</span>
              <strong>{primaryWallet?.profile.followingCount ?? 0}</strong>
            </div>
            <div>
              <span>Groups</span>
              <strong>{session?.groups.length ?? 0}</strong>
            </div>
          </div>

          <div className="actionStack">
            {hasReownProjectId ? (
              <div className="appkitControls">
                <AppKitButton namespace="eip155" />
                <AppKitNetworkButton />
              </div>
            ) : (
              <>
                <div className="notice">
                  <AlertCircle size={16} />
                  Set VITE_REOWN_PROJECT_ID to enable Reown AppKit and
                  WalletConnect. Local injected wallets are available without it.
                </div>
                {!account.isConnected ? (
                  connectors.map((connector) => (
                    <button
                      className="commandButton"
                      type="button"
                      disabled={isConnecting}
                      key={connector.uid}
                      onClick={() => connect({ connector })}
                    >
                      <Wallet size={16} />
                      Connect {connector.name}
                    </button>
                  ))
                ) : (
                  <button
                    className="commandButton secondary"
                    type="button"
                    onClick={() => disconnect()}
                  >
                    <Wallet size={16} />
                    Disconnect wallet
                  </button>
                )}
              </>
            )}

            <button
              className="commandButton"
              type="button"
              disabled={!account.isConnected || signIn.isSigningMessage}
              onClick={signIn.handleSignIn}
            >
              <ShieldCheck size={16} />
              {signIn.isSigningMessage ? "Signing..." : "Sign in with Ethereum"}
            </button>

            <button
              className="commandButton secondary"
              type="button"
              disabled={
                !account.isConnected ||
                !session?.authenticated ||
                linkWallet.isSigningMessage
              }
              onClick={linkWallet.handleSignIn}
            >
              <LinkIcon size={16} />
              {linkWallet.isSigningMessage ? "Signing..." : "Link current wallet"}
            </button>
          </div>

          {siweError || logoutMutation.error ? (
            <div className="notice errorNotice">
              <AlertCircle size={16} />
              {siweError || logoutMutation.error?.message}
            </div>
          ) : null}

          {nonceMetadata ? (
            <div className="notice">
              <ShieldCheck size={16} />
              Nonce TTL: {nonceMetadata.expirationTime / 1000}s
            </div>
          ) : null}
        </div>

        <div className="panel profilePanel">
          <div className="panelHeader">
            <div>
              <h2>ENS and EthID</h2>
              <p>Stored profile data plus live Ethereum Identity Kit preview.</p>
            </div>
            {primaryWallet?.profile.url ? (
              <a
                className="iconButton"
                href={primaryWallet.profile.url}
                target="_blank"
                rel="noreferrer"
                title="Open profile"
              >
                <ExternalLink size={16} />
              </a>
            ) : null}
          </div>

          {addressOrName ? (
            <div className="profilePreview">
              <ProfileCard addressOrName={addressOrName} />
            </div>
          ) : (
            <div className="empty">
              <UserRound size={24} />
              Profile enrichment appears after SIWE verification.
            </div>
          )}

          <form className="searchForm" onSubmit={submitProfileSearch}>
            <input
              value={profileQuery}
              onChange={(event) => setProfileQuery(event.target.value)}
              placeholder="ENS name or address"
              aria-label="ENS name or address"
            />
            <button
              className="iconButton"
              type="submit"
              title="Fetch public profile"
              disabled={publicProfile.isPending}
            >
              <Search size={18} />
            </button>
          </form>

          {publicProfile.data ? (
            <pre className="jsonPreview">
              {JSON.stringify(publicProfile.data.profile, null, 2)}
            </pre>
          ) : null}
          {publicProfile.error ? (
            <div className="notice errorNotice">
              <AlertCircle size={16} />
              {publicProfile.error.message}
            </div>
          ) : null}
        </div>

        <div className="panel widePanel">
          <div className="panelHeader">
            <div>
              <h2>Linked wallets</h2>
              <p>Manage SIWE wallets attached to the Django user.</p>
            </div>
          </div>
          <div className="walletList">
            {session?.wallets.map((wallet) => (
              <WalletRow
                wallet={wallet}
                key={wallet.id}
                canUnlink={!wallet.isPrimary}
                isPending={unlinkMutation.isPending}
                onUnlink={() => unlinkMutation.mutate(wallet.id)}
              />
            ))}
            {!session?.wallets.length ? (
              <div className="empty">
                <Wallet size={24} />
                No linked wallets yet.
              </div>
            ) : null}
          </div>
        </div>

        <div className="panel widePanel">
          <div className="panelHeader">
            <div>
              <h2>Token gates</h2>
              <p>Django groups synchronized from configured SIWE gates.</p>
            </div>
          </div>
          {session ? <GateList session={session} /> : null}
          {sessionQuery.isError ? (
            <div className="notice errorNotice">
              <AlertCircle size={16} />
              {sessionQuery.error.message}
            </div>
          ) : null}
        </div>
      </section>
    </main>
  );
}
