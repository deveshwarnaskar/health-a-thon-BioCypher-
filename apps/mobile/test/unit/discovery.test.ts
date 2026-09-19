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

  // =========================================================================
  // Gate 10P / Keycloak 24 Regression Tests (A through G)
  // =========================================================================

  it("A: accepts a real Keycloak 24 discovery document containing standard RFC 8414 metadata", async () => {
    const keycloakDoc = {
      issuer: "http://192.168.31.177:8080/realms/thali",
      authorization_endpoint: "http://192.168.31.177:8080/realms/thali/protocol/openid-connect/auth",
      token_endpoint: "http://192.168.31.177:8080/realms/thali/protocol/openid-connect/token",
      introspection_endpoint: "http://192.168.31.177:8080/realms/thali/protocol/openid-connect/token/introspect",
      userinfo_endpoint: "http://192.168.31.177:8080/realms/thali/protocol/openid-connect/userinfo",
      end_session_endpoint: "http://192.168.31.177:8080/realms/thali/protocol/openid-connect/logout",
      frontchannel_logout_session_supported: true,
      frontchannel_logout_supported: true,
      jwks_uri: "http://192.168.31.177:8080/realms/thali/protocol/openid-connect/certs",
      check_session_iframe: "http://192.168.31.177:8080/realms/thali/protocol/openid-connect/login-status-iframe.html",
      grant_types_supported: [
        "authorization_code",
        "implicit",
        "refresh_token",
        "password",
        "client_credentials",
      ],
      response_types_supported: [
        "code",
        "none",
        "id_token",
        "token",
        "id_token token",
        "code id_token",
        "code token",
        "code id_token token",
      ],
      subject_types_supported: ["public", "pairwise"],
      id_token_signing_alg_values_supported: ["RS256", "ES256", "HS256"],
      scopes_supported: ["openid", "offline_access", "email", "profile"],
      code_challenge_methods_supported: ["plain", "S256"],
      revocation_endpoint: "http://192.168.31.177:8080/realms/thali/protocol/openid-connect/revoke",
      revocation_endpoint_auth_methods_supported: [
        "private_key_jwt",
        "client_secret_basic",
      ],
      device_authorization_endpoint: "http://192.168.31.177:8080/realms/thali/protocol/openid-connect/auth/device",
      pushed_authorization_request_endpoint: "http://192.168.31.177:8080/realms/thali/protocol/openid-connect/ext/par/request",
      authorization_response_iss_parameter_supported: true,
    };

    const fetchImpl = vi.fn(async () => new Response(JSON.stringify(keycloakDoc), { status: 200 }));
    const result = await discoverOidc("http://192.168.31.177:8080/realms/thali", fetchImpl);

    expect(result.issuer).toBe("http://192.168.31.177:8080/realms/thali");
    expect(result.authorizationEndpoint).toBe("http://192.168.31.177:8080/realms/thali/protocol/openid-connect/auth");
    expect(result.tokenEndpoint).toBe("http://192.168.31.177:8080/realms/thali/protocol/openid-connect/token");
    expect(result.jwksUri).toBe("http://192.168.31.177:8080/realms/thali/protocol/openid-connect/certs");
    expect(result.endSessionEndpoint).toBe("http://192.168.31.177:8080/realms/thali/protocol/openid-connect/logout");
    expect(result.userInfoEndpoint).toBe("http://192.168.31.177:8080/realms/thali/protocol/openid-connect/userinfo");
    expect(result.codeChallengeMethodsSupported).toEqual(["plain", "S256"]);
  });

  it("B: rejects discovery document when issuer does not match requested issuer URL", async () => {
    const mismatchedDoc = {
      issuer: "http://attacker-controlled-idp.test/realms/evil",
      authorization_endpoint: "http://attacker-controlled-idp.test/auth",
      token_endpoint: "http://attacker-controlled-idp.test/token",
    };

    const fetchImpl = vi.fn(async () => new Response(JSON.stringify(mismatchedDoc), { status: 200 }));
    const err = await discoverOidc("http://keycloak.test/realms/test", fetchImpl).catch((e) => e);

    expect(err).toBeDefined();
    expect(err.kind).toBe("OIDC_DISCOVERY_ERROR");
    expect(err.message).toContain("issuer mismatch");
  });

  it("B: accepts matching issuer with trailing slash variation (normalization)", async () => {
    const doc = {
      issuer: "http://keycloak.test/realms/test/",
      authorization_endpoint: "http://keycloak.test/auth",
      token_endpoint: "http://keycloak.test/token",
    };

    const fetchImpl = vi.fn(async () => new Response(JSON.stringify(doc), { status: 200 }));
    const result = await discoverOidc("http://keycloak.test/realms/test", fetchImpl);
    expect(result.issuer).toBe("http://keycloak.test/realms/test/");
  });

  it("C: rejects discovery document when authorization_endpoint is missing", async () => {
    const doc = {
      issuer: "http://keycloak.test/realms/test",
      token_endpoint: "http://keycloak.test/token",
    };

    const fetchImpl = vi.fn(async () => new Response(JSON.stringify(doc), { status: 200 }));
    const err = await discoverOidc("http://keycloak.test/realms/test", fetchImpl).catch((e) => e);

    expect(err).toBeDefined();
    expect(err.kind).toBe("OIDC_DISCOVERY_ERROR");
    expect(err.message).toContain("authorization_endpoint");
  });

  it("D: rejects discovery document when token_endpoint is missing", async () => {
    const doc = {
      issuer: "http://keycloak.test/realms/test",
      authorization_endpoint: "http://keycloak.test/auth",
    };

    const fetchImpl = vi.fn(async () => new Response(JSON.stringify(doc), { status: 200 }));
    const err = await discoverOidc("http://keycloak.test/realms/test", fetchImpl).catch((e) => e);

    expect(err).toBeDefined();
    expect(err.kind).toBe("OIDC_DISCOVERY_ERROR");
    expect(err.message).toContain("token_endpoint");
  });

  it("E: rejects discovery document with malformed endpoint URLs", async () => {
    const malformedAuth = {
      issuer: "http://keycloak.test/realms/test",
      authorization_endpoint: "not-a-valid-url",
      token_endpoint: "http://keycloak.test/token",
    };

    const fetchImpl = vi.fn(async () => new Response(JSON.stringify(malformedAuth), { status: 200 }));
    const errAuth = await discoverOidc("http://keycloak.test/realms/test", fetchImpl).catch((e) => e);

    expect(errAuth).toBeDefined();
    expect(errAuth.kind).toBe("OIDC_DISCOVERY_ERROR");
    expect(errAuth.message).toContain("authorization_endpoint");

    const malformedToken = {
      issuer: "http://keycloak.test/realms/test",
      authorization_endpoint: "http://keycloak.test/auth",
      token_endpoint: "also-not-a-url",
    };

    const fetchImpl2 = vi.fn(async () => new Response(JSON.stringify(malformedToken), { status: 200 }));
    const errToken = await discoverOidc("http://keycloak.test/realms/test", fetchImpl2).catch((e) => e);

    expect(errToken).toBeDefined();
    expect(errToken.kind).toBe("OIDC_DISCOVERY_ERROR");
    expect(errToken.message).toContain("token_endpoint");
  });

  it("F: validates PKCE S256 support (rejects plain-only, accepts S256)", async () => {
    // Plain only: MUST be rejected
    const plainOnlyDoc = {
      issuer: "http://keycloak.test/realms/test",
      authorization_endpoint: "http://keycloak.test/auth",
      token_endpoint: "http://keycloak.test/token",
      code_challenge_methods_supported: ["plain"],
    };

    const fetchImplPlain = vi.fn(async () => new Response(JSON.stringify(plainOnlyDoc), { status: 200 }));
    const errPlain = await discoverOidc("http://keycloak.test/realms/test", fetchImplPlain).catch((e) => e);

    expect(errPlain).toBeDefined();
    expect(errPlain.kind).toBe("OIDC_DISCOVERY_ERROR");
    expect(errPlain.message).toContain("S256");

    // S256 only: MUST be accepted
    const s256Doc = {
      issuer: "http://keycloak.test/realms/test",
      authorization_endpoint: "http://keycloak.test/auth",
      token_endpoint: "http://keycloak.test/token",
      code_challenge_methods_supported: ["S256"],
    };

    const fetchImplS256 = vi.fn(async () => new Response(JSON.stringify(s256Doc), { status: 200 }));
    const resS256 = await discoverOidc("http://keycloak.test/realms/test", fetchImplS256);
    expect(resS256.codeChallengeMethodsSupported).toEqual(["S256"]);

    // Both plain and S256: MUST be accepted (server supports S256)
    const bothDoc = {
      issuer: "http://keycloak.test/realms/test",
      authorization_endpoint: "http://keycloak.test/auth",
      token_endpoint: "http://keycloak.test/token",
      code_challenge_methods_supported: ["plain", "S256"],
    };

    resetDiscoveryCache();
    const fetchImplBoth = vi.fn(async () => new Response(JSON.stringify(bothDoc), { status: 200 }));
    const resBoth = await discoverOidc("http://keycloak.test/realms/test", fetchImplBoth);
    expect(resBoth.codeChallengeMethodsSupported).toEqual(["plain", "S256"]);
  });

  it("G: preserves strict security requirements while ignoring unneeded metadata", async () => {
    const docWithExtras = {
      issuer: "http://keycloak.test/realms/test",
      authorization_endpoint: "http://keycloak.test/auth",
      token_endpoint: "http://keycloak.test/token",
      untrusted_injected_field: "malicious_payload",
      arbitrary_internal_metadata: { evil: true },
    };

    const fetchImpl = vi.fn(async () => new Response(JSON.stringify(docWithExtras), { status: 200 }));
    const result = await discoverOidc("http://keycloak.test/realms/test", fetchImpl);

    // Operational endpoints are strictly preserved
    expect(result.authorizationEndpoint).toBe("http://keycloak.test/auth");
    expect(result.tokenEndpoint).toBe("http://keycloak.test/token");
    expect(result.issuer).toBe("http://keycloak.test/realms/test");

    // Unrecognized metadata is stripped and NOT exposed on the operational discovery model
    expect((result as Record<string, unknown>).untrusted_injected_field).toBeUndefined();
    expect((result as Record<string, unknown>).arbitrary_internal_metadata).toBeUndefined();
  });
});
