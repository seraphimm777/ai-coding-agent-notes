const mongoose = require('mongoose');

const NoteSchema = mongoose.Schema({
    title: String,
    content: String,
    // Tags let users organise notes into freeform categories (e.g. "work", "recipe").
    // Stored lowercase/trimmed so filtering and search are case-insensitive and
    // "Work" / "work " always match the same tag.
    tags: {
        type: [String],
        default: [],
        set: (tags) => Array.isArray(tags)
            ? [...new Set(tags.map(t => String(t).trim().toLowerCase()).filter(Boolean))]
            : []
    }
}, {
    timestamps: true
});

// Text index on title/content powers relevance-ranked keyword search (?search=).
NoteSchema.index({ title: 'text', content: 'text' });
// Index on tags speeds up tag filtering (?tag=) and the distinct-tags lookup.
NoteSchema.index({ tags: 1 });

module.exports = mongoose.model('Note', NoteSchema);
