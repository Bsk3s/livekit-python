#!/bin/bash

echo "🌟 Testing Render Deployment of Spiritual Guidance Voice Agent API"
echo "🕐 Test started at: $(date)"
echo "======================================================================"

# Possible Render URLs to test
URLS=(
    "https://spiritual-token-api.onrender.com"
    "https://spiritual-token-api-latest.onrender.com"
    "https://spiritual-guidance-api.onrender.com"
    "https://heavenly-hub-api.onrender.com"
)

WORKING_URLS=()

# Test each URL
for url in "${URLS[@]}"; do
    echo ""
    echo "🔗 Testing base URL: $url"
    echo "------------------------------------------------"
    
    # Test root endpoint
    echo "🔍 Testing: $url/"
    response=$(curl -s -w "%{http_code}" -o /tmp/response.json "$url/" 2>/dev/null)
    http_code="${response: -3}"
    
    if [ "$http_code" = "200" ]; then
        echo "✅ SUCCESS: $url/"
        echo "   Status: $http_code"
        echo "   Response:"
        cat /tmp/response.json | python3 -m json.tool 2>/dev/null || cat /tmp/response.json
        WORKING_URLS+=("$url")
        
        # Test health endpoint
        echo ""
        echo "🔍 Testing: $url/health"
        health_response=$(curl -s -w "%{http_code}" -o /tmp/health.json "$url/health" 2>/dev/null)
        health_code="${health_response: -3}"
        
        if [ "$health_code" = "200" ]; then
            echo "✅ HEALTH SUCCESS: $url/health"
            echo "   Response:"
            cat /tmp/health.json | python3 -m json.tool 2>/dev/null || cat /tmp/health.json
        else
            echo "❌ HEALTH FAILED: $url/health - Status: $health_code"
        fi
        
        # Test token generation
        echo ""
        echo "🔍 Testing: $url/api/spiritual-token"
        token_response=$(curl -s -w "%{http_code}" -X POST \
            -H "Content-Type: application/json" \
            -d '{"character": "adina", "user_id": "test-user-123"}' \
            -o /tmp/token.json "$url/api/spiritual-token" 2>/dev/null)
        token_code="${token_response: -3}"
        
        if [ "$token_code" = "200" ]; then
            echo "✅ TOKEN SUCCESS: $url/api/spiritual-token"
            echo "   Response:"
            cat /tmp/token.json | python3 -m json.tool 2>/dev/null || cat /tmp/token.json
        else
            echo "❌ TOKEN FAILED: $url/api/spiritual-token - Status: $token_code"
            echo "   Response:"
            cat /tmp/token.json 2>/dev/null || echo "No response"
        fi
        
    else
        echo "❌ FAILED: $url/ - Status: $http_code"
    fi
done

echo ""
echo "======================================================================"
echo "📊 DEPLOYMENT TEST SUMMARY"
echo "======================================================================"

if [ ${#WORKING_URLS[@]} -gt 0 ]; then
    echo "✅ Found ${#WORKING_URLS[@]} working URL(s):"
    for url in "${WORKING_URLS[@]}"; do
        echo "   🔗 $url"
    done
    
    echo ""
    echo "🎯 Your API is successfully deployed!"
    echo "📖 API Documentation: ${WORKING_URLS[0]}/docs"
    echo "🏥 Health Check: ${WORKING_URLS[0]}/health"
    echo "🎭 Token Generation: ${WORKING_URLS[0]}/api/spiritual-token"
    
    echo ""
    echo "📱 For mobile testing, use this base URL:"
    echo "   ${WORKING_URLS[0]}"
    
else
    echo "❌ No working URLs found!"
    echo ""
    echo "🔍 Troubleshooting steps:"
    echo "1. Check your Render dashboard for the actual service URL"
    echo "2. Verify the service is running and not crashed"
    echo "3. Check environment variables are set correctly"
    echo "4. Review deployment logs for errors"
    
    echo ""
    echo "💡 Manual URL check:"
    echo "   Go to your Render dashboard and find the actual URL"
    echo "   Then test manually: curl https://YOUR-ACTUAL-URL.onrender.com/health"
fi

# Cleanup
rm -f /tmp/response.json /tmp/health.json /tmp/token.json

echo ""
echo "🕐 Test completed at: $(date)" 