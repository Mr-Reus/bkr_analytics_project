import axios from 'axios';

// Базова URL-адреса вашого FastAPI бекенду
const BASE_URL = 'http://127.0.0.1:8000';

export const api = axios.create({
    baseURL: BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Інтерцептор для автоматичного додавання JWT токена
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('access_token');
        if (token && config.headers) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// Інтерцептор для обробки прострочених токенів (401)
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('access_token');
            window.location.href = '/'; // Перенаправлення на сторінку входу
        }
        return Promise.reject(error);
    }
);