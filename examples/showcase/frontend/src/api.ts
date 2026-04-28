export type WalletProfile = {
  displayName: string;
  avatar: string;
  url: string;
  followersCount: number;
  followingCount: number;
  ens: {
    name: string;
    avatar: string;
    description: string;
    header: string;
    records: Record<string, unknown>;
  };
  ethIdentityKit: Record<string, unknown>;
};

export type WalletIdentity = {
  id: number;
  address: string;
  chainId: number;
  caip10: string;
  ensName: string;
  ensAvatar: string;
  displayName: string;
  avatar: string;
  profile: WalletProfile;
  ethereumIdentityKit: {
    addressOrName: string;
    profileUrl: string;
  };
  isPrimary: boolean;
  lastLogin: string | null;
};

export type SessionUser = {
  id: string;
  isAuthenticated: boolean;
  username: string;
};

export type GateStatus = {
  name: string;
  label: string;
  description: string;
  group: string;
  active: boolean;
};

export type SessionResponse = {
  authenticated: boolean;
  user: SessionUser | null;
  wallet: WalletIdentity | null;
  wallets: WalletIdentity[];
  groups: string[];
  gates: GateStatus[];
};

export type NonceResponse = {
  nonce: string;
  statement: string;
  ethereumIdentityKit: {
    statement: string;
    expirationTime: number;
  };
};

export type PublicProfileResponse = {
  success: boolean;
  profile: Record<string, unknown>;
};

let lastNonce: NonceResponse | null = null;

export function getLastNonceMetadata() {
  return lastNonce?.ethereumIdentityKit;
}

function csrfToken(): string {
  const match = document.cookie
    .split("; ")
    .find((row) => row.startsWith("csrftoken="));
  return match ? decodeURIComponent(match.split("=")[1]) : "";
}

async function parseJson<T>(response: Response): Promise<T> {
  const data = (await response.json().catch(() => ({}))) as T & {
    message?: string;
  };
  if (!response.ok) {
    throw new Error(data.message || `Request failed with ${response.status}`);
  }
  return data;
}

export async function fetchSession(): Promise<SessionResponse> {
  const response = await fetch("/api/showcase/session/", {
    credentials: "include",
  });
  return parseJson<SessionResponse>(response);
}

export async function getNonce(): Promise<string> {
  const response = await fetch("/auth/siwe/nonce/", {
    credentials: "include",
  });
  const data = await parseJson<NonceResponse>(response);
  lastNonce = data;
  return data.nonce;
}

async function postSignature(
  url: string,
  message: string,
  signature: string,
): Promise<boolean> {
  const response = await fetch(url, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken(),
    },
    body: JSON.stringify({ message, signature }),
  });
  await parseJson(response);
  return true;
}

export function verifySignature(message: string, signature: string) {
  return postSignature("/auth/siwe/verify/", message, signature);
}

export function linkSignature(message: string, signature: string) {
  return postSignature("/auth/siwe/link/", message, signature);
}

export async function logout(): Promise<void> {
  const response = await fetch("/auth/siwe/logout/", {
    method: "POST",
    credentials: "include",
    headers: {
      "X-CSRFToken": csrfToken(),
    },
  });
  await parseJson(response);
}

export async function unlinkWallet(walletId: number): Promise<void> {
  const response = await fetch(`/auth/siwe/wallets/${walletId}/`, {
    method: "DELETE",
    credentials: "include",
    headers: {
      "X-CSRFToken": csrfToken(),
    },
  });
  await parseJson(response);
}

export async function fetchPublicProfile(
  addressOrName: string,
): Promise<PublicProfileResponse> {
  const response = await fetch(
    `/auth/siwe/profile/${encodeURIComponent(addressOrName)}/`,
    { credentials: "include" },
  );
  return parseJson<PublicProfileResponse>(response);
}
