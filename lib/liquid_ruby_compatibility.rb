# The github-pages 223 dependency pins Liquid 4.0.3. Liquid still calls the
# no-op taint APIs that Ruby removed in 3.2, so restore only those two methods
# until the GitHub Pages dependency moves to a newer Liquid release.
if Gem::Version.new(RUBY_VERSION) >= Gem::Version.new("3.2")
  class Object
    def tainted?
      false
    end unless method_defined?(:tainted?)

    def untaint
      self
    end unless method_defined?(:untaint)
  end
end
