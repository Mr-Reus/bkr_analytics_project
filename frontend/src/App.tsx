import React from 'react'; // Додано імпорт React
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';

const PrivateRoute = ({ children }: { children: React.ReactNode }) => {
    const token = localStorage.getItem('access_token');
    return token ? <>{children}</> : <Navigate to="/" />;
};

function App() {
    return (
        <BrowserRouter>
            <Routes>
                <Route path="/" element={<Login />} />
                <Route 
                    path="/dashboard" 
                    element={
                        <PrivateRoute>
                            <Dashboard />
                        </PrivateRoute>
                    } 
                />
            </Routes>
        </BrowserRouter>
    );
}

export default App;