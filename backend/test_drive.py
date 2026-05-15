from dotenv import load_dotenv
load_dotenv()

from drive_tool import get_drive_service
import os

service = get_drive_service()
folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
print('Folder ID:', folder_id)

# Test 1 - with folder
query1 = "'" + folder_id + "' in parents and trashed = false"
print('\nTest 1 - with folder ID:')
results1 = service.files().list(q=query1, pageSize=10, fields='files(id, name, mimeType)').execute()
files1 = results1.get('files', [])
print('Found', len(files1), 'files')
for f in files1:
    print(' -', f['name'])

# Test 2 - without folder (all drive)
query2 = "mimeType = 'application/pdf' and trashed = false"
print('\nTest 2 - PDFs without folder restriction:')
results2 = service.files().list(q=query2, pageSize=10, fields='files(id, name, mimeType)').execute()
files2 = results2.get('files', [])
print('Found', len(files2), 'files')
for f in files2:
    print(' -', f['name'])

# Test 3 - all files
query3 = "trashed = false"
print('\nTest 3 - all files:')
results3 = service.files().list(q=query3, pageSize=10, fields='files(id, name, mimeType)').execute()
files3 = results3.get('files', [])
print('Found', len(files3), 'files')
for f in files3:
    print(' -', f['name'])