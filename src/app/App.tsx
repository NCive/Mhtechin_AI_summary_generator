import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { AppLayout } from '../components/layout/AppLayout';
import { AppRoutes } from './routes';

export const App: React.FC = () => {
  return (
    <BrowserRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <AppLayout>
        <AppRoutes />
      </AppLayout>
    </BrowserRouter>
  );
};

export default App;
