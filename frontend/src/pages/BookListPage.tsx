import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { booksApi } from '../services/api'
import type { BookList, Book } from '../types'

export default function BookListPage() {
  const navigate = useNavigate()
  const [bookLists, setBookLists] = useState<BookList[]>([])
  const [selectedList, setSelectedList] = useState<BookList | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch form state
  const [fetchType, setFetchType] = useState<'amazon' | 'csv'>('amazon')
  const [amazonUrl, setAmazonUrl] = useState('')
  const [listName, setListName] = useState('')
  const [csvFile, setCsvFile] = useState<File | null>(null)

  useEffect(() => {
    loadBookLists()
  }, [])

  const loadBookLists = async () => {
    try {
      const lists = await booksApi.getBookLists()
      setBookLists(lists)
    } catch (err) {
      console.error('Failed to load book lists:', err)
    }
  }

  const handleFetchAmazon = async () => {
    if (!listName.trim()) {
      setError('请输入书单名称')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const bookList = await booksApi.fetchAmazonList(
        listName,
        amazonUrl || undefined
      )
      setBookLists([bookList, ...bookLists])
      setSelectedList(bookList)
      setListName('')
      setAmazonUrl('')
    } catch (err: any) {
      setError(err.response?.data?.detail || '获取书单失败')
    } finally {
      setLoading(false)
    }
  }

  const handleUploadCSV = async () => {
    if (!csvFile || !listName.trim()) {
      setError('请选择 CSV 文件并输入书单名称')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const bookList = await booksApi.uploadCSV(csvFile, listName)
      setBookLists([bookList, ...bookLists])
      setSelectedList(bookList)
      setListName('')
      setCsvFile(null)
    } catch (err: any) {
      setError(err.response?.data?.detail || '上传 CSV 失败')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectBook = (book: Book) => {
    navigate(`/research/${book.id}`)
  }

  return (
    <div className="px-4 py-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">书单管理</h1>

      {/* Fetch Books Section */}
      <div className="bg-white shadow rounded-lg p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          获取书单
        </h2>

        <div className="mb-4">
          <div className="flex space-x-4 mb-4">
            <button
              onClick={() => setFetchType('amazon')}
              className={`px-4 py-2 rounded ${
                fetchType === 'amazon'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-700'
              }`}
            >
              Amazon 榜单
            </button>
            <button
              onClick={() => setFetchType('csv')}
              className={`px-4 py-2 rounded ${
                fetchType === 'csv'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-700'
              }`}
            >
              CSV 导入
            </button>
          </div>

          {fetchType === 'amazon' ? (
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  书单名称 *
                </label>
                <input
                  type="text"
                  value={listName}
                  onChange={(e) => setListName(e.target.value)}
                  placeholder="例如：Amazon Best Sellers 2024"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Amazon 榜单 URL（可选）
                </label>
                <input
                  type="text"
                  value={amazonUrl}
                  onChange={(e) => setAmazonUrl(e.target.value)}
                  placeholder="留空使用默认 Best Sellers 榜单"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <button
                onClick={handleFetchAmazon}
                disabled={loading}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400"
              >
                {loading ? '获取中...' : '获取书单'}
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  书单名称 *
                </label>
                <input
                  type="text"
                  value={listName}
                  onChange={(e) => setListName(e.target.value)}
                  placeholder="例如：2024 精选书单"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  CSV 文件 *
                </label>
                <input
                  type="file"
                  accept=".csv"
                  onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
                <p className="text-xs text-gray-500 mt-1">
                  CSV 必须包含 title 列，可选 author、isbn、description 等
                </p>
              </div>
              <button
                onClick={handleUploadCSV}
                disabled={loading}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400"
              >
                {loading ? '上传中...' : '上传 CSV'}
              </button>
            </div>
          )}

          {error && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
              {error}
            </div>
          )}
        </div>
      </div>

      {/* Book Lists */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          已获取的书单
        </h2>

        {bookLists.length === 0 ? (
          <p className="text-gray-500">暂无书单，请先获取书单</p>
        ) : (
          <div className="space-y-4">
            {bookLists.map((list) => (
              <div
                key={list.id}
                className="border border-gray-200 rounded-lg p-4 cursor-pointer hover:bg-gray-50"
                onClick={() => setSelectedList(list)}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-medium text-gray-900">{list.name}</h3>
                    <p className="text-sm text-gray-500">
                      来源：{list.source_type} | 获取时间：
                      {new Date(list.fetched_at).toLocaleString('zh-CN')}
                    </p>
                  </div>
                  <span className="text-sm text-gray-500">
                    {list.books?.length || 0} 本书
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Selected Book List Details */}
      {selectedList && (
        <div className="mt-6 bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            {selectedList.name} - 书籍列表
          </h2>

          {selectedList.books && selectedList.books.length > 0 ? (
            <div className="space-y-3">
              {selectedList.books.map((book) => (
                <div
                  key={book.id}
                  className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 cursor-pointer"
                  onClick={() => handleSelectBook(book)}
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2">
                        {book.rank && (
                          <span className="text-sm font-medium text-gray-500">
                            #{book.rank}
                          </span>
                        )}
                        <h3 className="font-medium text-gray-900">
                          {book.title}
                        </h3>
                      </div>
                      {book.author && (
                        <p className="text-sm text-gray-600 mt-1">
                          作者：{book.author}
                        </p>
                      )}
                      {book.description && (
                        <p className="text-sm text-gray-500 mt-2 line-clamp-2">
                          {book.description}
                        </p>
                      )}
                      <div className="flex space-x-4 mt-2 text-xs text-gray-500">
                        {book.isbn && <span>ISBN: {book.isbn}</span>}
                        {book.asin && <span>ASIN: {book.asin}</span>}
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleSelectBook(book)
                      }}
                      className="ml-4 px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
                    >
                      开始研究
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500">此书单暂无书籍</p>
          )}
        </div>
      )}
    </div>
  )
}
