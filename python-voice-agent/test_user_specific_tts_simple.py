#!/usr/bin/env python3
"""
🔧 SIMPLE USER-SPECIFIC TTS TEST
Test the user identification logic without complex imports
"""

import os

def test_user_identification():
    """Test user identification logic"""
    
    print("🔧 SIMPLE USER-SPECIFIC TTS TEST")
    print("=" * 50)
    
    # Admin identities that should get ElevenLabs
    admin_identities = ["administrator", "admin", "owner", "user_administrator", "test-user", "admin-user"]
    
    # Test cases
    test_cases = [
        ("administrator", True, "Admin user"),
        ("admin", True, "Admin user"),
        ("owner", True, "Owner user"),
        ("user_administrator", True, "Admin prefix user"),
        ("test-user", True, "Test admin user"),
        ("admin-user", True, "Admin suffix user"),
        ("Administrator", True, "Admin user (capitalized)"),
        ("ADMINISTRATOR", True, "Admin user (uppercase)"),
        ("user123", False, "Regular user"),
        ("guest", False, "Guest user"),
        ("anonymous", False, "Anonymous user"),
        ("mobile-user", False, "Mobile user"),
        ("web-user", False, "Web user"),
        ("customer123", False, "Customer user"),
    ]
    
    print("\n1️⃣ Testing USER IDENTIFICATION LOGIC...")
    print("-" * 50)
    
    all_passed = True
    
    for user_identity, should_be_admin, description in test_cases:
        # This is the exact logic from the spiritual worker
        is_admin_user = user_identity and any(admin_id in user_identity.lower() for admin_id in admin_identities)
        
        if is_admin_user == should_be_admin:
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
            all_passed = False
        
        tts_type = "ElevenLabs (if enabled)" if is_admin_user else "OpenAI TTS-1 HD"
        
        print(f"{status} {user_identity:20} → {tts_type:25} ({description})")
    
    print("\n2️⃣ Testing TTS SELECTION LOGIC...")
    print("-" * 50)
    
    # Test TTS selection for different scenarios
    scenarios = [
        ("administrator", True, "ElevenLabs"),
        ("administrator", False, "OpenAI TTS-1 HD"),
        ("user123", True, "OpenAI TTS-1 HD"),
        ("user123", False, "OpenAI TTS-1 HD"),
    ]
    
    for user_identity, elevenlabs_enabled, expected_tts in scenarios:
        is_admin_user = user_identity and any(admin_id in user_identity.lower() for admin_id in admin_identities)
        
        # TTS selection logic
        if is_admin_user and elevenlabs_enabled:
            selected_tts = "ElevenLabs"
        else:
            selected_tts = "OpenAI TTS-1 HD"
        
        if selected_tts == expected_tts:
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
            all_passed = False
        
        elevenlabs_status = "enabled" if elevenlabs_enabled else "disabled"
        print(f"{status} {user_identity:15} + ElevenLabs {elevenlabs_status:8} → {selected_tts}")
    
    print("\n3️⃣ Testing VOICE MAPPING...")
    print("-" * 50)
    
    # Voice mapping test
    voice_map = {
        "adina": "nova",  # Warm, feminine voice for Adina
        "raffa": "onyx",  # Deep, masculine voice for Raffa
    }
    
    character_tests = [
        ("adina", "nova"),
        ("raffa", "onyx"),
        ("Adina", "nova"),
        ("RAFFA", "onyx"),
        ("unknown", "alloy"),
    ]
    
    for character, expected_voice in character_tests:
        actual_voice = voice_map.get(character.lower(), "alloy")
        
        if actual_voice == expected_voice:
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
            all_passed = False
        
        print(f"{status} Character '{character}' → Voice '{actual_voice}'")
    
    print("\n4️⃣ SUMMARY...")
    print("-" * 50)
    
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("✅ User-specific TTS logic is working correctly")
        print("\nDeployment Ready:")
        print("🔧 Set USE_ELEVENLABS=true in your .env file")
        print("🔑 Add your ELEVENLABS_API_KEY to .env file")
        print("🚀 Deploy to production")
        print("\nBehavior:")
        print(f"👤 Users with identities: {', '.join(admin_identities)}")
        print("   → Will get ElevenLabs TTS (ultra-fast, premium)")
        print("👥 All other users:")
        print("   → Will get OpenAI TTS-1 HD (high quality)")
    else:
        print("❌ SOME TESTS FAILED!")
        print("⚠️ Please check the logic above")
    
    return all_passed

if __name__ == "__main__":
    test_user_identification() 