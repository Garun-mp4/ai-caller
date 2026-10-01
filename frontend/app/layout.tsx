import '@fontsource-variable/inter';
import './globals.css';
import Shell from '@/components/Shell';

export const metadata = {
  title: 'AI Call Agent',
  description: 'Рабочее пространство для лидов, кампаний и звонков',
  icons: { icon: [{ url: '/icon.svg', type: 'image/svg+xml' }] },
};

const themeScript = `try { const saved = localStorage.getItem('ai-caller-theme'); document.documentElement.dataset.theme = saved === 'dark' ? 'dark' : 'light'; } catch (_) { document.documentElement.dataset.theme = 'light'; }`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="ru" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{ __html: themeScript }}/></head><body><Shell>{children}</Shell></body></html>;
}
