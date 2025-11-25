// Manual test script to verify git context extraction
import { getStagedDiff } from './dist/git.js';

console.log('Testing git context extraction...\n');

getStagedDiff()
  .then(result => {
    console.log('Git Context Result:');
    console.log('==================');
    console.log('Branch:', result.branch);
    console.log('Staged Files:', result.stagedFiles);
    console.log('Diff Length:', result.diff.length, 'characters');
    console.log('Error:', result.error || 'None');
    
    if (result.error) {
      console.log('\n❌ Error occurred:', result.error);
    } else {
      console.log('\n✅ Successfully retrieved git context');
      if (result.stagedFiles.length === 0) {
        console.log('ℹ️  No files currently staged');
      } else {
        console.log('\nStaged files:');
        result.stagedFiles.forEach(file => console.log('  -', file));
      }
    }
  })
  .catch(error => {
    console.error('❌ Unexpected error:', error);
  });
