import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom'
import ThemeSearchPage from './pages/ThemeSearchPage'
import BookListPage from './pages/BookListPage'
import ResearchPage from './pages/ResearchPage'
import SingleBookPage from './pages/SingleBookPage'

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        <nav className="bg-white shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16">
              <div className="flex space-x-8">
                <Link
                  to="/"
                  className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-900"
                >
                  主题找书
                </Link>
                <Link
                  to="/single-book"
                  className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-500 hover:text-gray-900"
                >
                  指定书籍
                </Link>
                <Link
                  to="/books"
                  className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-500 hover:text-gray-900"
                >
                  历史书单
                </Link>
              </div>
            </div>
          </div>
        </nav>

        <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
          <Routes>
            <Route path="/" element={<ThemeSearchPage />} />
            <Route path="/books" element={<BookListPage />} />
            <Route path="/single-book" element={<SingleBookPage />} />
            <Route path="/research/:bookId" element={<ResearchPage />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

export default App
