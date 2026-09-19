import ImmersiveBackground from './ImmersiveBackground'
import Navbar from './Navbar'
import TickerTape from './TickerTape'

function PageLayout({ children }) {
  return (
    <div className="min-h-screen text-slate-100">
      <ImmersiveBackground />
      <Navbar />
      <TickerTape />
      <main className="relative z-10 mx-auto max-w-7xl px-4 py-8 sm:px-6">{children}</main>
    </div>
  )
}

export default PageLayout