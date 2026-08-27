module.exports = (app) => {
    const notes = require('../controllers/note.controller.js');

    // Create a new Note
    app.post('/notes', notes.create);

    // Retrieve all Notes (supports ?search=keyword and ?tag=name for
    // organising/searching notes)
    app.get('/notes', notes.findAll);

    // Retrieve the distinct list of tags currently in use
    // NOTE: must be registered before '/notes/:noteId' so Express doesn't
    // treat "tags" as a noteId.
    app.get('/notes/tags', notes.listTags);

    // Retrieve a single Note with noteId
    app.get('/notes/:noteId', notes.findOne);

    // Update a Note with noteId
    app.put('/notes/:noteId', notes.update);

    // Delete a Note with noteId
    app.delete('/notes/:noteId', notes.delete);
}