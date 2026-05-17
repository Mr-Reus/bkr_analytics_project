/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Button, TextField, Typography, Paper, Alert, CssBaseline } from '@mui/material';
import  api  from '../api/axios';

export const Login: React.FC = () => {
    const navigate = useNavigate();
    const [isRegister, setIsRegister] = useState(false);
    
    const [companyName, setCompanyName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [inviteCode, setInviteCode] = useState(''); 
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            if (isRegister) {
                const response = await api.post('/api/auth/register/admin', {
                    company_name: companyName,
                    email: email,
                    password: password,
                    invite_code: inviteCode
                });
                localStorage.setItem('access_token', response.data.access_token);
                navigate('/dashboard');
            } else {
                const formData = new URLSearchParams();
                formData.append('username', email);
                formData.append('password', password);
                
                const response = await api.post('/api/auth/token', formData, {
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
                });
                localStorage.setItem('access_token', response.data.access_token);
                navigate('/dashboard');
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Сталася помилка авторизації');
        } finally {
            setLoading(false);
        }
    };

    return (
        <Box sx={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f4f6f8' }}>
            <CssBaseline />
            <Paper elevation={3} sx={{ p: 5, width: '100%', maxWidth: 450, borderRadius: 3 }}>
                <Typography variant="h4" sx={{ fontWeight: 800, mb: 1, textAlign: 'center', color: '#1976d2' }}>
                    BKR Analytics
                </Typography>
                <Typography variant="body2" sx={{ color: '#616161', mb: 4, textAlign: 'center' }}>
                    {isRegister ? 'Створіть робочий простір для вашої компанії' : 'Увійдіть до системи аналітики'}
                </Typography>

                {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

                <form onSubmit={handleSubmit}>
                    {isRegister && (
                        <>
                            <TextField
                                fullWidth
                                label="Назва компанії"
                                variant="outlined"
                                margin="normal"
                                required
                                value={companyName}
                                onChange={(e) => setCompanyName(e.target.value)}
                            />
                            <TextField
                                fullWidth
                                label="Invite Code (Код доступу)"
                                variant="outlined"
                                margin="normal"
                                required
                                value={inviteCode}
                                onChange={(e) => setInviteCode(e.target.value)}
                                helperText="Видається адміністратором платформи"
                            />
                        </>
                    )}
                    <TextField
                        fullWidth
                        label="Електронна пошта"
                        type="email"
                        variant="outlined"
                        margin="normal"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                    />
                    <TextField
                        fullWidth
                        label="Пароль"
                        type="password"
                        variant="outlined"
                        margin="normal"
                        required
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                    />
                    <Button
                        type="submit"
                        fullWidth
                        variant="contained"
                        disabled={loading}
                        sx={{ mt: 3, mb: 2, py: 1.5, fontWeight: 'bold', fontSize: '1rem' }}
                    >
                        {loading ? 'Обробка...' : (isRegister ? 'ЗАРЕЄСТРУВАТИ КОМПАНІЮ' : 'УВІЙТИ')}
                    </Button>
                </form>

                <Button fullWidth onClick={() => { setIsRegister(!isRegister); setError(''); }} sx={{ color: '#757575' }}>
                    {isRegister ? 'Вже є акаунт? Увійти' : 'Нова компанія? Зареєструватися'}
                </Button>
            </Paper>
        </Box>
    );
};