import './globals.css'; import Shell from '@/components/Shell';
export const metadata={title:'AI Call Agent',description:'Local AI calling CRM MVP'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="ru"><body><Shell>{children}</Shell></body></html>}
