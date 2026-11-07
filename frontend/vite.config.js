import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({plugins:[react()],server:{port:5173,proxy:{'/health':'http://127.0.0.1:8000','/overview':'http://127.0.0.1:8000','/policy':'http://127.0.0.1:8000','/customers':'http://127.0.0.1:8000','/invoices':'http://127.0.0.1:8000','/requests':'http://127.0.0.1:8000','/audit':'http://127.0.0.1:8000','/agent':'http://127.0.0.1:8000'}}});
