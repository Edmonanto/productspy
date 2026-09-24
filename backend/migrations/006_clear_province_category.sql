-- 1688's search payload has no category field; the provider was storing the
-- supplier's province there (浙江, 广东, ...). The dashboard read that column as
-- a product category, so its category filter matched nothing for any source
-- and every category selection returned an empty list — which the frontend
-- then silently replaced with demo products.
--
-- The provider no longer writes it. Clear what it already wrote, rather than
-- leave a province masquerading as a category.

update products set category = null
 where source = '1688' and category is not null;
