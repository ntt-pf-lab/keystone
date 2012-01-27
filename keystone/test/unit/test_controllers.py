import unittest2 as unittest
from webob import Request
import keystone.controllers as controllers


class TestControllers(unittest.TestCase):
    """Unit tests for controllers/__init__.py."""

    def test_configure_pagination_invalid(self):
        """Verify invalid page_limit returns a ValueError"""
        conf_dict = {'page_limit': 'abc'}
        self.assertRaises(ValueError, controllers.configure_pagination,
                            conf_dict)

    def test_pagination_limit_default(self):
        """Test the pagination limit returned is the default one (i.e. 10)."""
        request = Request.blank('/tenants')

        conf_dict = {}
        controllers.configure_pagination(conf_dict)
        (marker, limit, url) = controllers.get_marker_limit_and_url(request)
        self.assertEqual(limit, 10)

    def test_pagination_limit_specified_in_conf(self):
        """Test the pagination limit returned is the one specified."""
        request = Request.blank('/tenants')

        conf_dict = {'page_limit': 20}
        controllers.configure_pagination(conf_dict)
        (marker, limit, url) = controllers.get_marker_limit_and_url(request)
        self.assertEqual(limit, conf_dict['page_limit'])

    def test_pagination_limit_specified_in_request(self):
        """
        Test the pagination limit returned is the one specified in
        the request.
        """
        request = Request.blank('/tenants?limit=5')

        conf_dict = {'page_limit': 20}
        controllers.configure_pagination(conf_dict)
        (marker, limit, url) = controllers.get_marker_limit_and_url(request)
        self.assertEqual(limit, '5')
