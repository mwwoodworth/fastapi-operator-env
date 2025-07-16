import React from 'react';
import ProductTable from '../../../components/ProductTable';

export default function ProductsPage() {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Products</h2>
      <ProductTable />
    </div>
  );
}
