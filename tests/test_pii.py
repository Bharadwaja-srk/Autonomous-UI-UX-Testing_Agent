import pytest
from backend.pii_redaction import PIIRedactionEngine
from backend.schemas import UIElement, BoundingBox

def test_mask_text():
    engine = PIIRedactionEngine()
    
    text1 = "User email is john.doe@example.com and phone is 555-1234."
    masked1 = engine.mask_text(text1)
    assert "[EMAIL_REDACTED]" in masked1
    assert "john.doe@example.com" not in masked1
    
    text2 = "My CC is 4111-1111-1111-1111 for the order."
    masked2 = engine.mask_text(text2)
    assert "[CREDIT_CARD_REDACTED]" in masked2
    assert "4111-1111-1111-1111" not in masked2
    
    text3 = "SSN is 123-45-6789"
    masked3 = engine.mask_text(text3)
    assert "[SSN_REDACTED]" in masked3
    assert "123-45-6789" not in masked3

def test_is_sensitive_element():
    engine = PIIRedactionEngine()
    
    el_password = UIElement(id=1, tag="input", role="password")
    assert engine.is_sensitive_element(el_password) == True
    
    el_normal = UIElement(id=2, tag="input", name="username")
    assert engine.is_sensitive_element(el_normal) == False
    
    el_cc = UIElement(id=3, tag="input", name="credit-card")
    assert engine.is_sensitive_element(el_cc) == True
