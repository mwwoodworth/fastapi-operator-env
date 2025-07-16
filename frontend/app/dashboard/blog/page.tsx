'use client';
import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import LoadingCard from '../../../components/LoadingCard';
import StatusIndicator from '../../../components/StatusIndicator';

interface BlogPost {
  id: string;
  title: string;
  excerpt: string;
  content?: string;
  author: string;
  publishedAt: Date;
  readTime: string;
  tags: string[];
  status: 'draft' | 'published' | 'archived';
}

export default function BlogPage() {
  const [posts, setPosts] = useState<BlogPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    // Simulate loading blog posts
    setTimeout(() => {
      const mockPosts: BlogPost[] = [
        {
          id: '1',
          title: 'Building AI-Native Applications with FastAPI and Claude',
          excerpt: 'Learn how to create powerful AI-driven applications using FastAPI for the backend and Claude for intelligent processing...',
          author: 'BrainOps Team',
          publishedAt: new Date('2024-01-15'),
          readTime: '8 min read',
          tags: ['AI', 'FastAPI', 'Claude', 'Tutorial'],
          status: 'published'
        },
        {
          id: '2',
          title: 'RAG Memory Systems: Best Practices and Implementation',
          excerpt: 'Discover how to implement efficient Retrieval-Augmented Generation systems with vector databases and embeddings...',
          author: 'AI Research',
          publishedAt: new Date('2024-01-10'),
          readTime: '12 min read',
          tags: ['RAG', 'Vector DB', 'Memory', 'AI'],
          status: 'published'
        },
        {
          id: '3',
          title: 'Automating Business Workflows with Make.com',
          excerpt: 'A comprehensive guide to creating powerful automation scenarios that connect your business tools...',
          author: 'Operations Team',
          publishedAt: new Date('2024-01-05'),
          readTime: '6 min read',
          tags: ['Automation', 'Make.com', 'Workflows'],
          status: 'published'
        },
        {
          id: '4',
          title: 'The Future of AI Operators: 2024 Trends',
          excerpt: 'Exploring emerging trends in AI-powered business operations and what to expect in the coming year...',
          author: 'Strategy Team',
          publishedAt: new Date('2024-01-01'),
          readTime: '10 min read',
          tags: ['AI', 'Trends', 'Strategy'],
          status: 'draft'
        }
      ];
      setPosts(mockPosts);
      setLoading(false);
    }, 1000);
  }, []);

  const allTags = Array.from(new Set(posts.flatMap(post => post.tags)));

  const filteredPosts = posts.filter(post => {
    const matchesTag = !selectedTag || post.tags.includes(selectedTag);
    const matchesSearch = !searchQuery || 
      post.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      post.excerpt.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesTag && matchesSearch;
  });

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold flex items-center space-x-3">
            <span className="text-4xl">📝</span>
            <span className="bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
              Knowledge Base
            </span>
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            Technical articles, tutorials, and insights from BrainOps
          </p>
        </div>
        <Link
          href="/dashboard/blog/new"
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors flex items-center space-x-2"
        >
          <span>✍️</span>
          <span>New Post</span>
        </Link>
      </div>

      {/* Search and Filters */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1">
            <input
              type="text"
              placeholder="Search articles..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-4 py-2 rounded-lg border dark:border-gray-700 bg-gray-50 dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setSelectedTag(null)}
              className={`px-3 py-1 rounded-full text-sm transition-colors ${
                !selectedTag 
                  ? 'bg-indigo-600 text-white' 
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              All Posts
            </button>
            {allTags.map(tag => (
              <button
                key={tag}
                onClick={() => setSelectedTag(tag)}
                className={`px-3 py-1 rounded-full text-sm transition-colors ${
                  selectedTag === tag 
                    ? 'bg-indigo-600 text-white' 
                    : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                }`}
              >
                {tag}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Blog Posts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {loading ? (
          <>
            <LoadingCard />
            <LoadingCard />
            <LoadingCard />
            <LoadingCard />
          </>
        ) : filteredPosts.length === 0 ? (
          <div className="col-span-2 text-center py-12">
            <div className="text-gray-400 mb-4">
              <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <p className="text-gray-600 dark:text-gray-400">No posts found matching your criteria</p>
          </div>
        ) : (
          filteredPosts.map(post => (
            <article
              key={post.id}
              className="bg-white dark:bg-gray-800 rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 overflow-hidden group"
            >
              <div className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center space-x-2">
                    <StatusIndicator 
                      status={post.status === 'published' ? 'online' : post.status === 'draft' ? 'pending' : 'offline'} 
                    />
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      {post.status === 'draft' ? 'Draft' : post.publishedAt.toLocaleDateString()}
                    </span>
                  </div>
                  <span className="text-sm text-gray-500">{post.readTime}</span>
                </div>
                
                <h3 className="text-xl font-semibold mb-2 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                  {post.title}
                </h3>
                
                <p className="text-gray-600 dark:text-gray-400 mb-4 line-clamp-2">
                  {post.excerpt}
                </p>
                
                <div className="flex items-center justify-between">
                  <div className="flex flex-wrap gap-2">
                    {post.tags.map(tag => (
                      <span
                        key={tag}
                        className="px-2 py-1 bg-gray-100 dark:bg-gray-700 text-xs rounded-full"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                  
                  <Link
                    href={`/dashboard/blog/${post.id}`}
                    className="text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 flex items-center space-x-1 text-sm font-medium"
                  >
                    <span>Read more</span>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </Link>
                </div>
              </div>
              
              <div className="px-6 py-3 bg-gray-50 dark:bg-gray-900 border-t dark:border-gray-700">
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  By {post.author}
                </p>
              </div>
            </article>
          ))
        )}
      </div>

      {/* Stats Section */}
      {!loading && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Content Statistics</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-indigo-600 dark:text-indigo-400">
                {posts.filter(p => p.status === 'published').length}
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Published</p>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
                {posts.filter(p => p.status === 'draft').length}
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Drafts</p>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                {allTags.length}
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Topics</p>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                {Math.round(posts.reduce((acc, post) => acc + parseInt(post.readTime), 0) / posts.length)} min
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Avg Read Time</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}