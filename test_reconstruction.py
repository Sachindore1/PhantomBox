# test_phantombox.py
import requests
import hashlib
import os

def test_upload_download():
    print("🧪 Testing PhantomBox upload and download...")
    
    # Create a test PDF file
    pdf_content = b'''%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources << >>
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(PhantomBox Test PDF) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f
0000000010 00000 n
0000000053 00000 n
0000000112 00000 n
0000000204 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
308
%%EOF'''
    
    # Save test file
    with open('test_file.pdf', 'wb') as f:
        f.write(pdf_content)
    
    print(f"Created test PDF: {len(pdf_content)} bytes")
    
    # Test upload
    print("\n📤 Testing upload...")
    files = {'file': ('test_file.pdf', pdf_content, 'application/pdf')}
    
    try:
        response = requests.post('http://localhost:8000/api/upload', files=files)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Upload successful!")
            print(f"   File ID: {result.get('file_id')}")
            print(f"   Original filename: {result.get('original_filename')}")
            
            file_id = result.get('file_id')
            
            # Test download
            print("\n📥 Testing download...")
            download_response = requests.get(f'http://localhost:8000/api/request_download/{file_id}')
            
            if download_response.status_code == 200:
                download_result = download_response.json()
                print(f"✅ Download request successful!")
                print(f"   Download token: {download_result.get('download_token')}")
                print(f"   File size: {download_result.get('file_size')} bytes")
                
                # Download the file
                download_token = download_result.get('download_token')
                file_response = requests.get(f'http://localhost:8000/api/download/{download_token}')
                
                if file_response.status_code == 200:
                    downloaded_data = file_response.content
                    print(f"✅ File downloaded successfully!")
                    print(f"   Downloaded size: {len(downloaded_data)} bytes")
                    
                    # Verify
                    if pdf_content == downloaded_data:
                        print("🎉 SUCCESS: File integrity verified!")
                        # Save downloaded file
                        with open('downloaded_test.pdf', 'wb') as f:
                            f.write(downloaded_data)
                        print("Saved as 'downloaded_test.pdf'")
                    else:
                        print("⚠️ Warning: Downloaded file differs from original")
                else:
                    print(f"❌ File download failed: {file_response.status_code}")
            else:
                print(f"❌ Download request failed: {download_response.status_code}")
                print(f"   Error: {download_response.text}")
        else:
            print(f"❌ Upload failed: {response.status_code}")
            print(f"   Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Cleanup
    if os.path.exists('test_file.pdf'):
        os.remove('test_file.pdf')
    if os.path.exists('downloaded_test.pdf'):
        os.remove('downloaded_test.pdf')

if __name__ == "__main__":
    test_upload_download()