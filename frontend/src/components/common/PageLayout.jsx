import ImmersiveBackground from './ImmersiveBackground'
import Navbar from './Navbar'
import TickerTape from './TickerTape'

function PageLayout({ children }) {
  return (
    <div className="min-h-screen text-slate-100 lg:grid lg:grid-cols-[14rem_minmax(0,1fr)]">
      <ImmersiveBackground />
      <Navbar />
      <TickerTape />
      <main className="relative z-10 min-w-0 lg:col-start-2 lg:row-start-2">
        <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">{children}</div>
      </main>
    </div>
  )
}

export default PageLayout