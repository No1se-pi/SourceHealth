import React, { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { TopBar } from '../components/layout/TopBar';
import { Footer } from '../components/layout/Footer';
import { AppearanceModal } from '../components/layout/AppearanceModal';

export const AppLayout: React.FC = () => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [appearanceOpen, setAppearanceOpen] = useState(false);

  // Close mobile drawer when resizing to desktop >= 768px
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth >= 768) {
        setMobileOpen(false);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <div className="sc-app-shell">
      {/* SourceCraft Left Application Sidebar */}
      <Sidebar
        mobileOpen={mobileOpen}
        onClose={() => setMobileOpen(false)}
        onOpenAppearance={() => setAppearanceOpen(true)}
      />

      {/* Mobile Drawer Backdrop */}
      {mobileOpen && (
        <div
          className="sc-mobile-backdrop"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Main Workspace Area (Fluid width, not 1200px max-width clamp) */}
      <div className="sc-workspace">
        <TopBar
          onToggleMobile={() => setMobileOpen((prev) => !prev)}
          onOpenAppearance={() => setAppearanceOpen(true)}
        />
        <main className="sc-workspace-main">
          <Outlet />
        </main>
        <Footer />
      </div>

      {/* SourceCraft Appearance Settings Dialog */}
      <AppearanceModal
        isOpen={appearanceOpen}
        onClose={() => setAppearanceOpen(false)}
      />
    </div>
  );
};
