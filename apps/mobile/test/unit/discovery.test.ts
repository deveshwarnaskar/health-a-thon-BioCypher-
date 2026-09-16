import { describe, it, expect, vi, beforeEach } from "vitest";
import { discoverOidc, resetDiscoveryCache, type OidcDiscovery } from "../../src/auth/discovery";

beforeEach(() => {
  resetDiscoveryCache();
});

function validDoc(): OidcDiscovery {
  return {
    issuer: "http://keycloak.test/realms/test",
    authorizationEndpoint: "http://keycloak.test/auth",
    tokenEndpoint: "http://keycloak.test/token",
    revocationEndpoint: "http://keycloak.test/revoke",
    endSessionEndpoint: "http://keycloak.test/logout",
  };
}

describe("discovery", () => {
  it("fetches and returns the discovery document", async () => {
    const doc = validDoc();
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify({
      issuer: doc.issuer,
      authorization_endpoint: doc.authorizationEndpoint,
      token_endpoint: doc.tokenEndpoint,
      revocation_endpoint: doc.revocationEndpoint,
      end_session_endpoint: doc.endSessionEndpoint,
    }), { status: 200 }));
    const result = await discoverOidc("http://keycloak.test/realms/test", fetchImpl);
    expect(result.authorizationEndpoint).toBe(doc.authorizationEndpoint);
    expect(fetchImpl).toHaveBeenCalledOnce();
  });

  it("caches the result for the same issuer", async () => {
    const doc = validDoc();
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify({
      issuer: doc.issuer,
      authorization_endpoint: doc.authorizationEndpoint,
      token_endpoint: doc.tokenEndpoint,
    }), { status: 200 }));
    await discoverOidc("http://keycloak.test/realms/test", fetchImpl);
    await discoverOidc("http://keycloak.test/realms/test", fetchImpl);
    expect(fetchImpl).toHaveBeenCalledOnce();
  });

  it("throws on non-200 response", async () => {
    const fetchImpl = vi.fn(async () => new Response("Not Found", { status: 404 }));
    const result = await discoverOidc("http://keycloak.test/realms/test", fetchImpl).then(
      () => null,
      (err) => err
    );
    expect(result).toBeDefined();
    expect(result.kind).toBe("OIDC_DISCOVERY_ERROR");
  });

  it("throws on invalid JSON body", async () => {
    const fetchImpl = vi.fn(async () => new Response("not json", { status: 200 }));
    const result = await discoverOidc("http://keycloak.test/realms/test", fetchImpl).then(
      () => null,
      (err) => err
    );
    expect(result).toBeDefined();
    expect(result.kind).toBe("OIDC_DISCOVERY_ERROR");
  });

  it("throws when required fields are missing", async () => {
    const incompleteDoc = { issuer: "http://test" };
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify(incompleteDoc), { status: 200 }));
    const result = await discoverOidc("http://keycloak.test/realms/test", fetchImpl).then(
      () => null,
      (err) => err
    );
    expect(result).toBeDefined();
    expect(result.kind).toBe("OIDC_DISCOVERY_ERROR");
  });

  it("resetDiscoveryCache clears the cache", async () => {
    const doc = validDoc();
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify({
      issuer: doc.issuer,
      authorization_endpoint: doc.authorizationEndpoint,
      token_endpoint: doc.tokenEndpoint,
    }), { status: 200 }));
    await discoverOidc("http://keycloak.test/realms/test", fetchImpl);
    resetDiscoveryCache();
    await discoverOidc("http://keycloak.test/realms/test", fetchImpl);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });
});
