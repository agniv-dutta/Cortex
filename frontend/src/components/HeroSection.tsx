import React from 'react';
import type { HeroSectionProps } from '../types/dashboard';
import { SearchInterface } from './SearchInterface';

export const HeroSection: React.FC<HeroSectionProps> = ({
  onSearchSubmit,
}) => {
  return (
    <div className="w-full max-w-6xl mx-auto px-4">
      <SearchInterface
        onSubmitQuery={(data) => {
          if (onSearchSubmit) {
            onSearchSubmit(data.query);
          }
        }}
      />
    </div>
  );
};
