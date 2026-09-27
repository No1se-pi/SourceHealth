import React, { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { TopBar } from '../components/layout/TopBar';
import { Footer } from '../components/layout/Footer';
import { AppearanceModal } from '../components/layout/AppearanceModal';
import { KeyboardHelpModal } from '../components/layout/KeyboardHelpModal';

export const AppLayout: React.FC = () => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [appearanceOpen, setAppearanceOpen] = useState(false);
  const [keyboardHelpOpen, setKeyboardHelpOpen] = useState(false);

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

  // Global '?' shortcut for keyboard help
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT' ||
          target.isContentEditable)
      ) {
        return;
      }
      if (e.key === '?' || (e.shiftKey && e.key === '/')) {
        e.preventDefault();
        setKeyboardHelpOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div className="sc-app-shell">
      {/* Skip to Content Link (A11y J01) */}
      <a href="#main-content" className="sc-skip-to-content">
        Перейти к основному содержимому
      </a>

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
        <main className="sc-workspace-main" id="main-content" tabIndex={-1}>
          <Outlet />
        </main>
        <Footer />
      </div>

      {/* SourceCraft Appearance Settings Dialog */}
      <AppearanceModal
        isOpen={appearanceOpen}
        onClose={() => setAppearanceOpen(false)}
      />

      {/* Keyboard Shortcuts Help Dialog */}
      <KeyboardHelpModal
        isOpen={keyboardHelpOpen}
        onClose={() => setKeyboardHelpOpen(false)}
      />
    </div>
  );
};
