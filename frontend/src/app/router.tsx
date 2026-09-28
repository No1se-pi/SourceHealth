import React from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AppLayout } from '../layouts/AppLayout';
import { LeaderboardPage } from '../pages/LeaderboardPage';
import { RepositoryPage } from '../pages/RepositoryPage';
import { AnalysisPage } from '../pages/AnalysisPage';
import { AuthCallbackPage } from '../pages/AuthCallbackPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { SourceCraftPage } from '../pages/SourceCraftPage';
import { DemoPage } from '../pages/DemoPage';
import { ProfilePage } from '../pages/ProfilePage';
import { DevelopersPage } from '../pages/DevelopersPage';
import { ComparePage } from '../pages/ComparePage';
import { QueuePage } from '../pages/QueuePage';
import { ScrollToTop } from '../components/common/ScrollToTop';

export const AppRouter: React.FC = () => {
  return (
    <BrowserRouter>
      <ScrollToTop />
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<LeaderboardPage />} />
          <Route path="/repositories/:id" element={<RepositoryPage />} />
          <Route path="/analyses/:id" element={<AnalysisPage />} />
          <Route path="/auth/callback" element={<AuthCallbackPage />} />
          <Route path="/sourcecraft" element={<SourceCraftPage />} />
          <Route path="/demo" element={<DemoPage />} />
          <Route path="/queue" element={<QueuePage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/developers" element={<DevelopersPage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};
