import axios, { AxiosError } from 'axios';
import { APP_CONFIG } from '../constants/appConstants';

export const apiClient = axios.create({
  baseURL: APP_CONFIG.API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // Log error for debugging while preserving original error
    console.error('[API Error]:', error.response?.status, error.message);
    return Promise.reject(error);
  }
);
