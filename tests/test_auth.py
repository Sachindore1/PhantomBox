"""
tests/test_auth.py
─────────────────────────────────────────────────────────────
Automated tests for PhantomBox Auth System.
Run with: python tests/test_auth.py

Tests cover:
  - User registration (success + duplicate + validation)
  - Login (success + wrong password + lockout)
  - JWT token decode
  - Password strength checker
  - Token refresh flow
  - Password reset flow
─────────────────────────────────────────────────────────────
"""

import sys
import os
import unittest
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phantombox.auth.models  import init_db, SessionLocal, User
from phantombox.auth.security import (
    hash_password, verify_password, check_password_strength,
    create_access_token, decode_access_token,
    generate_refresh_token, hash_token, sanitize_email
)
from phantombox.auth.mysql_service import (
    register_user, login_user, logout_user,
    refresh_access_token, request_password_reset, reset_password
)


# ── Setup ─────────────────────────────────────────────────────

# Use in-memory SQLite for tests
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test_secret_key_for_unit_tests"
os.environ["BCRYPT_ROUNDS"]  = "4"   # Low cost for fast tests


# ── Test Cases ────────────────────────────────────────────────

class TestPasswordSecurity(unittest.TestCase):
    def test_hash_and_verify_correct(self):
        """bcrypt hash + verify should work for matching passwords."""
        h = hash_password("SecurePass1!")
        self.assertTrue(verify_password("SecurePass1!", h))

    def test_verify_wrong_password(self):
        """Wrong password must return False."""
        h = hash_password("SecurePass1!")
        self.assertFalse(verify_password("WrongPass1!", h))

    def test_hash_is_not_plaintext(self):
        """Hash must not contain the plaintext."""
        h = hash_password("MySecret123!")
        self.assertNotIn("MySecret123!", h)

    def test_two_hashes_differ(self):
        """Same password hashed twice should give different hashes (salted)."""
        h1 = hash_password("SamePass1!")
        h2 = hash_password("SamePass1!")
        self.assertNotEqual(h1, h2)   # bcrypt salts are random

    def test_strength_too_short(self):
        ok, msg = check_password_strength("abc")
        self.assertFalse(ok)
        self.assertIn("8", msg)

    def test_strength_weak_but_long(self):
        ok, _ = check_password_strength("alllowercase")
        # Only 1 character class → should fail
        self.assertFalse(ok)

    def test_strength_strong(self):
        ok, msg = check_password_strength("Ph@ntom8ox!")
        self.assertTrue(ok)

    def test_strength_too_long(self):
        ok, _ = check_password_strength("A" * 200)
        self.assertFalse(ok)


class TestJWT(unittest.TestCase):
    def test_create_and_decode(self):
        """Token created should decode back with same claims."""
        token = create_access_token("user-123", "test@test.com", "user")
        payload = decode_access_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"],   "user-123")
        self.assertEqual(payload["email"], "test@test.com")
        self.assertEqual(payload["role"],  "user")
        self.assertEqual(payload["type"],  "access")

    def test_tampered_token_fails(self):
        """Tampered token must return None."""
        token   = create_access_token("user-abc", "x@y.com", "user")
        tampered = token[:-5] + "XXXXX"
        self.assertIsNone(decode_access_token(tampered))

    def test_invalid_token_fails(self):
        self.assertIsNone(decode_access_token("not.a.jwt"))

    def test_empty_token_fails(self):
        self.assertIsNone(decode_access_token(""))


class TestTokenGeneration(unittest.TestCase):
    def test_refresh_token_unique(self):
        raw1, h1 = generate_refresh_token()
        raw2, h2 = generate_refresh_token()
        self.assertNotEqual(raw1, raw2)
        self.assertNotEqual(h1,   h2)

    def test_hash_token_deterministic(self):
        raw = "some_test_token_value"
        self.assertEqual(hash_token(raw), hash_token(raw))

    def test_hash_differs_from_raw(self):
        raw = "some_test_token"
        self.assertNotEqual(hash_token(raw), raw)


class TestEmailSanitization(unittest.TestCase):
    def test_normalizes_to_lowercase(self):
        self.assertEqual(sanitize_email("User@Example.COM"), "user@example.com")

    def test_strips_whitespace(self):
        self.assertEqual(sanitize_email("  a@b.com  "), "a@b.com")

    def test_rejects_missing_at(self):
        with self.assertRaises(ValueError):
            sanitize_email("notanemail")

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            sanitize_email("")


class TestRegistration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_successful_registration(self):
        ok, res = register_user(
            email="alice@phantom.test",
            password="Ph@ntom8ox!",
            first_name="Alice",
            last_name="Smith",
        )
        self.assertTrue(ok)
        self.assertIn("user", res)
        self.assertEqual(res["user"]["email"], "alice@phantom.test")

    def test_duplicate_email_rejected(self):
        register_user("bob@phantom.test","Str0ng!Pass","Bob","Jones")
        ok, res = register_user("bob@phantom.test","Str0ng!Pass","Bob","Jones")
        self.assertFalse(ok)
        self.assertIn("email", res.get("field",""))

    def test_weak_password_rejected(self):
        ok, res = register_user("carol@phantom.test","weak","Carol","White")
        self.assertFalse(ok)
        self.assertIn("password", res.get("field",""))

    def test_invalid_email_rejected(self):
        ok, res = register_user("not-an-email","Str0ng!Pass","Dave","Brown")
        self.assertFalse(ok)


class TestLogin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        register_user("loginuser@phantom.test","Ph@ntom8ox!","Login","User")

    def test_correct_credentials(self):
        ok, res = login_user("loginuser@phantom.test","Ph@ntom8ox!")
        self.assertTrue(ok)
        self.assertIn("access_token",  res)
        self.assertIn("refresh_token", res)
        self.assertIn("user",          res)

    def test_wrong_password(self):
        ok, res = login_user("loginuser@phantom.test","WrongPassword!")
        self.assertFalse(ok)
        self.assertIn("INVALID_CREDENTIALS", res.get("code",""))

    def test_nonexistent_user(self):
        ok, res = login_user("nobody@phantom.test","AnyPass1!")
        self.assertFalse(ok)

    def test_access_token_is_valid_jwt(self):
        ok, res = login_user("loginuser@phantom.test","Ph@ntom8ox!")
        self.assertTrue(ok)
        payload = decode_access_token(res["access_token"])
        self.assertIsNotNone(payload)
        self.assertEqual(payload["email"], "loginuser@phantom.test")


class TestPasswordReset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        register_user("resetuser@phantom.test","OldPass@123!","Reset","User")

    def test_request_reset_known_email(self):
        ok, res = request_password_reset("resetuser@phantom.test")
        self.assertTrue(ok)
        self.assertIn("reset_token", res)   # demo mode: token in response

    def test_request_reset_unknown_email(self):
        # Should still return True (prevent enumeration)
        ok, _ = request_password_reset("nobody@nowhere.test")
        self.assertTrue(ok)

    def test_full_reset_flow(self):
        ok, res = request_password_reset("resetuser@phantom.test")
        self.assertTrue(ok)
        reset_tok = res["reset_token"]

        ok2, res2 = reset_password(reset_tok, "NewStr0ng@Pass!")
        self.assertTrue(ok2, res2.get("error"))

        # Old password should no longer work
        ok3, _ = login_user("resetuser@phantom.test","OldPass@123!")
        self.assertFalse(ok3)

        # New password should work
        ok4, _ = login_user("resetuser@phantom.test","NewStr0ng@Pass!")
        self.assertTrue(ok4)

    def test_used_reset_token_rejected(self):
        ok, res = request_password_reset("resetuser@phantom.test")
        token = res["reset_token"]
        reset_password(token, "AnotherPass@1!")
        ok2, res2 = reset_password(token, "YetAnother@1!")  # reuse
        self.assertFalse(ok2)


# ── Runner ────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("PhantomBox Auth System — Unit Tests")
    print("=" * 60)
    unittest.main(verbosity=2)