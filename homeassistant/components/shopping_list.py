"""Component to manage a shoppling list."""
import asyncio
import logging
import uuid

import voluptuous as vol

from homeassistant.const import HTTP_NOT_FOUND, HTTP_BAD_REQUEST
from homeassistant.core import callback
from homeassistant.components import http
from homeassistant.helpers import intent
import homeassistant.helpers.config_validation as cv


DOMAIN = 'shopping_list'
DEPENDENCIES = ['http']
_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = vol.Schema({DOMAIN: {}}, extra=vol.ALLOW_EXTRA)
EVENT = 'shopping_list_updated'
INTENT_ADD_ITEM = 'HassShoppingListAddItem'
INTENT_LAST_ITEMS = 'HassShoppingListLastItems'
ITEM_UPDATE_SCHEMA = vol.Schema({
    'complete': bool,
    'name': str,
})


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize the shopping list."""
    hass.data[DOMAIN] = ShoppingData([])
    intent.async_register(hass, AddItemIntent())
    intent.async_register(hass, ListTopItemsIntent())
    hass.http.register_view(ShoppingListView)
    hass.http.register_view(UpdateShoppingListItemView)
    hass.components.conversation.async_register(INTENT_ADD_ITEM, [
        'Add {item} to my shopping list',
    ])
    hass.components.conversation.async_register(INTENT_LAST_ITEMS, [
        'What is on my shopping list'
    ])
    hass.components.frontend.register_built_in_panel(
        'shopping-list', 'Shopping List', 'mdi:cart')
    return True


class ShoppingData:
    """Class to hold shopping list data."""

    def __init__(self, items):
        """Initialize the shopping list."""
        self.items = items

    def add(self, name):
        """Add a shopping list item."""
        self.items.append({
            'name': name,
            'id': uuid.uuid4().hex,
            'complete': False
        })

    def update(self, item_id, info):
        """Update a shopping list item."""
        item = next((itm for itm in self.items if itm['id'] == item_id), None)

        if item is None:
            raise KeyError

        info = ITEM_UPDATE_SCHEMA(info)
        item.update(info)
        return item

    def clear_completed(self):
        """Clear completed items."""
        self.items = [itm for itm in self.items if not itm['complete']]


class AddItemIntent(intent.IntentHandler):
    """Handle AddItem intents."""

    intent_type = INTENT_ADD_ITEM
    slot_schema = {
        'item': cv.string
    }

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        slots = self.async_validate_slots(intent_obj.slots)
        item = slots['item']['value']
        intent_obj.hass.data[DOMAIN].add(item)

        response = intent_obj.create_response()
        response.async_set_speech(
            "I've added {} to your shopping list".format(item))
        intent_obj.hass.bus.async_fire(EVENT)
        return response


class ListTopItemsIntent(intent.IntentHandler):
    """Handle AddItem intents."""

    intent_type = INTENT_LAST_ITEMS
    slot_schema = {
        'item': cv.string
    }

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        items = intent_obj.hass.data[DOMAIN].items[-5:]
        response = intent_obj.create_response()

        if not items:
            response.async_set_speech(
                "There are no items on your shopping list")
        else:
            response.async_set_speech(
                "These are the top {} items on your shopping list: {}".format(
                    min(len(items), 5),
                    ', '.join(itm['name'] for itm in reversed(items))))
        return response


class ShoppingListView(http.HomeAssistantView):
    """View to retrieve shopping list content."""

    url = '/api/shopping_list'
    name = "api:shopping_list"

    @callback
    def get(self, request):
        """Retrieve if API is running."""
        return self.json(request.app['hass'].data[DOMAIN].items)


class UpdateShoppingListItemView(http.HomeAssistantView):
    """View to retrieve shopping list content."""

    url = '/api/shopping_list/{item_id}'
    name = "api:shopping_list:id"

    @callback
    def post(self, request, item_id):
        """Retrieve if API is running."""
        data = yield from request.json()

        try:
            item = request.app['hass'].data[DOMAIN].update(item_id, data)
            request.app['hass'].bus.async_fire(EVENT)
            return self.json(item)
        except KeyError:
            return self.json_message('Item not found', HTTP_NOT_FOUND)
        except vol.Invalid:
            return self.json_message('Item not found', HTTP_BAD_REQUEST)
