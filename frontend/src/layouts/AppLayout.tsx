import React from 'react';
import { Outlet } from 'react-router-dom';
import { Header } from '../components/layout/Header';
import { Footer } from '../components/layout/Footer';
import { PageContainer } from '../components/common/PageContainer';

export const AppLayout: React.FC = () => {
  return (
    <>
      <Header />
      <main className="app-main">
        <PageContainer>
          <Outlet />
        </PageContainer>
      </main>
      <Footer />
    </>
  );
};
